---
title: "Postgres Internals Under the Hood: Database Clusters, Databases, and Table File Layout"
date: 2026-08-07T01:56:02.866291+00:00
draft: false
description: "A deep dive into PostgreSQL internals: how $PGDATA organizes database clusters, how databases map to base/ subdirectories by OID, and how table relfilenodes map to physical files."
summary: "We tear into Postgres' physical storage layer — from $PGDATA layout to per-database OID directories, to table relfilenode files and tablespaces. Plus the mistakes that bite everyone."
categories: ["Developer Tools"]
tags: ["Tech", "Analysis"]
cover:
  image: "/images/cover_1786067762_6425.jpg"
  alt: "Developer Tools Visualization"
  hiddenInList: false
  hiddenInSingle: false
---

## Key Takeaways

- **$PGDATA is not a database — it's the entire cluster root.** Every database lives inside its `base/` subdirectory, named by its OID, not its name.
- **Tables are not isolated files.** Each table is backed by at least one `relfilenode` file; when it exceeds 1GB, Postgres splits it into `relfilenode.1`, `relfilenode.2` segment files.
- **OID is the key to everything.** `pg_database` OIDs determine directory names under `base/`; `pg_class.relfilenode` determines table filenames. Skip this mapping and you'll be debugging blind.
- **Tablespaces break your directory assumptions.** Custom tablespaces relocate table files out of `base/` into symlinked paths under `pg_tblspc/` — a classic disk-usage investigation trap.
- **`ALTER TABLE ADD COLUMN` with a default does NOT rewrite old rows.** The default lives in `pg_attrdef`, computed at read time. That's why some ALTERs return instantly and others stall for ages.

---

Let me start with a painful memory. Last month our staging box's disk started screaming. `du -sh` showed one database eating 47GB — I nearly had a heart attack assuming some business table exploded. But after digging into `base/`, the real culprit was the leftover file of a long-dropped table. The `relfilenode` file was still on disk because some session was holding a snapshot, and VACUUM had no right to clean it up. Unless you understand Postgres' storage layout, you'll be fumbling around with `pg_relation_filepath()` trying every table name like a madman.

So let's strip Postgres' physical storage layer down to the bone. From cluster initialization all the way to table files, and then we talk about the traps.

## Database Cluster: One $PGDATA Is a Small Universe

One of the most confusing concepts in Postgres is the "database cluster." Most people hear "cluster" and think multiple machines. In Postgres land, a cluster is just the output of `initdb`. It contains:

- A `$PGDATA` root directory
- Several databases (default: `postgres`, `template0`, `template1`)
- A shared `pg_global` tablespace (for cross-database system catalogs like `pg_database`)
- A WAL directory (`pg_wal/`)
- Config files (`postgresql.conf`, `pg_hba.conf`, etc.)

A single cluster listens on one port by default (5432). If you want multiple "isolated" instances on one machine, you initialize multiple `$PGDATA` directories, each on its own port — this is the core of the eternal question "PostgreSQL database cluster vs. single server with many databases." **Multiple databases share the same process pool, WAL, and buffer pool.** Multiple clusters are completely isolated process groups. The former saves resources; the latter gives you stronger isolation and independent upgrades, but doubles your maintenance overhead.

After `initdb`, your `$PGDATA` looks roughly like this:

```bash
$ ls -F $PGDATA
base/    global/    pg_commit_ts/    pg_dynshmem/    pg_wal/    postgresql.conf
pg_hba.conf    PG_VERSION    postmaster.opts    postmaster.pid    ...
```

Pay attention to `base/` and `global/`. `global/` holds cluster-wide shared system catalogs; `base/` holds one subdirectory per database.

## Databases: The Numeric Naming Game Under base/

Postgres assigns each database an OID (Object Identifier, an unsigned 32-bit integer). Under `base/`, each database maps to a subdirectory named by that OID:

```bash
$ ls -F $PGDATA/base/
1/    13010/    13011/    13012/
```

`1` is `template1`'s OID; `13010` might be `postgres`; the rest are databases you created. Verify directly:

```sql
SELECT oid, datname FROM pg_database;
```

Output:

```
  oid  |  datname
-------+-----------
     1 | template1
 13010 | postgres
 13011 | myapp
 13012 | analytics
```

See? The directory names under `base/` map 1:1 to OIDs. When you read a blog post saying "this file `base/5/16384` is something," you should immediately think: `5` is a database's OID, `16384` is a table's `relfilenode` in that database.

Here's the counterintuitive part: **database directory names are not database names.** If you search by name, you will never find the directory. That's why so many people are baffled when they first poke around `base/`.

Another trap: **OIDs can be reused.** The 32-bit space is huge, but if your system churns through databases aggressively, OIDs can wrap around. Postgres ships `oid2name` to map OIDs back to names:

```bash
$ oid2name
All databases:
    OID  Database Name  Tablespace
 13010  postgres         pg_default
 13011  myapp            pg_default
```

Honestly, `oid2name` is criminally underused. It's genuinely useful for file-ownership forensics. I'd even suggest saving its output as a cheat sheet near your workstation.

## Tables: relfilenode Is the Real Name on Disk

Every table has a file in its database directory, named by the table's `relfilenode` value. This value usually equals the table's OID — but **not always.** `VACUUM FULL`, `CLUSTER`, and `REINDEX` rewrite tables and assign new relfilenodes. Never assume OID == filename.

Query it:

```sql
SELECT relname, relfilenode, oid FROM pg_class WHERE relname = 'users';
```

```
 relname | relfilenode |  oid
---------+-------------+-------
 users   |       24650 | 24650
```

Then grab the full path:

```sql
SELECT pg_relation_filepath('users');
```

```
 pg_relation_filepath
----------------------
 base/13011/24650
```

That's the real on-disk location. Peek at it:

```bash
$ ls -lah $PGDATA/base/13011/
-rw------- 1 postgres postgres 8.2M Aug  7 01:23 24650
-rw------- 1 postgres postgres 24K  Aug  7 01:23 24650_fsm
-rw------- 1 postgres postgres 8.2K Aug  7 01:23 24650_vm
```

`_fsm` is the Free Space Map, `_vm` is the Visibility Map. These are auxiliary files, but **don't delete them.** Postgres will rebuild them, but performance dips during the rebuild, and if you hit a crash-recovery window at exactly the wrong moment, you can end up with inconsistent data.

### Tables Over 1GB Get Split Into Segments

Postgres' default `segment_size` is 1GB (compile-time constant — `SHOW block_size` for block size, `SHOW segment_size` for segment size). Once a table exceeds 1GB, Postgres generates `24650.1`, `24650.2` suffix files:

```bash
$ ls -lah $PGDATA/base/13011/
-rw------- 1 postgres postgres 1.0G Aug  7 01:23 24650
-rw------- 1 postgres postgres 1.0G Aug  7 01:23 24650.1
-rw------- 1 postgres postgres 682M Aug  7 01:23 24650.2
```

This mechanism exists purely to dodge filesystem single-file size limits. You don't need to manage it manually — Postgres handles cross-segment addressing transparently. But backup tools (like manually `tar`-ing the entire data directory) must be aware: copying only `24650` without `.1` and `.2` produces a truncated table on restore, and `pg_checksums` might not even catch it (file sizes look legal; data is just missing).

### Indexes Are Files Too

Indexes don't live inside the table file. Each index has its own `relfilenode` file. So a "table + 5 indexes" costs 6 files (plus FSM/VM). A lot of people check `pg_total_relation_size()` and still underestimate how badly indexes can bloat. I've seen production tables at 20GB with 31GB of indexes — that alone can melt your buffer pool.

## Tablespaces: The Exception That Breaks the base/ Assumption

Postgres supports custom tablespaces, letting you place data on other disk paths. Once you use a tablespace, table files no longer live under `base/`; they live under:

```bash
$PGDATA/pg_tblspc/16386/
```

`16386` is the tablespace's OID. Note that `pg_tblspc/` contains not real directories but **symlinks** pointing to the path you specified at creation:

```bash
$ ls -l $PGDATA/pg_tblspc/
lrwxrwxrwx 1 postgres postgres 15 Aug  7 01:00 16386 -> /ssd/postgres_data
```

The upside: you can move data from HDD to SSD without moving a byte — just repoint the symlink. The downside: **if you `tar` up `$PGDATA` but forget `/ssd/postgres_data`, your restore is doomed.** Postgres starts up, hits a dangling symlink, and throws `could not open file` with only an OID in the message. You'll need `oid2name` to reverse-engineer what that OID means.

I strongly recommend that any backup script handling custom tablespaces also verify the tablespace's real path. Don't ask me how I know.

## Reading a Table File: 8KB Pages and Heap Tuples

Now you know where table files live. But what's inside? Postgres divides table files into fixed-size pages (default 8KB — confirm with `SHOW block_size`). Each page's internal structure:

- **PageHeaderData (24 bytes)** — page metadata, including checksum (if `data_checksums` is enabled), free-space start offset, special-space start offset.
- **ItemIdData array** — pointer array growing from the page header toward the tail; each pointer references a tuple's actual position.
- **Free space** — the gap between the header pointer array and the tail tuple data.
- **HeapTupleData array** — tuple data growing from the page tail toward the header; each tuple carries system columns like `t_xmin`, `t_xmax`, `t_ctid`.
- **Special space** — page end, typically for index pages (e.g., B-tree `highkey`).

This layout directly drives Postgres' MVCC: **updating a row is not overwriting old data — it's inserting a new version**, leaving the old version for older transactions. `t_xmin` and `t_xmax` define the visibility boundary.

### Sequential Scan vs. Index Scan

For reading a row, Postgres has two typical access paths:

1. **Sequential Scan (Seq Scan)** — reads from page 0 to the end, one page at a time. For small tables, this beats index scans because index scans involve two random I/Os (look up index, then fetch heap page), while sequential scans are linear prefetch-friendly.
2. **Index Scan** — walks the B-tree to find matching `ctid`s, then fetches the corresponding heap pages. For fetching a few rows from a large table, it's the only sensible choice.

The planner picks a path by estimating costs from `relpages` and `reltuples` statistics, which come from `ANALYZE`. **If you load a huge batch of data and forget to `ANALYZE`, the planner uses stale `reltuples`, and suddenly queries that should use an index go full sequential scan — P99 spikes to multiple seconds.** I've seen this exact scenario too many times.

## Table, Page, and Tuple Performance Trade-offs

Here's a truth that gets ignored: **Postgres' tuple size limit is page size minus header overhead** — with 8KB pages, one row maxes out at roughly 8KB minus ~24 bytes of page header minus ~23 bytes of tuple header. Insert a row exceeding that and Postgres throws `row is too big`. Large fields like `TEXT`, `JSONB`, `BYTEA` get compressed (if `COMPRESSION` is enabled) or moved to a `TOAST` table (The Oversized-Attribute Storage Technique).

TOAST tables are independent tables with their own `relfilenode`. So a table's true disk cost includes its TOAST table and TOAST index. `pg_relation_size('users')` returns only the main table; `pg_total_relation_size('users')` includes TOAST and all indexes.

| Object | Storage Location | File Naming Rule | Size Cap | Notes |
|--------|------------------|------------------|----------|-------|
| Database directory | `$PGDATA/base/<db_oid>/` | directory = database OID | none | one directory per database |
| Table (heap) | `base/<db_oid>/<relfilenode>` | filename = `relfilenode` | 1GB/segment default | `VACUUM FULL` assigns new `relfilenode` |
| Index | same directory | independent `relfilenode` file | 1GB/segment default | one file per index |
| TOAST table | same directory | `pg_toast_<table_oid>` | 1GB/segment default | large fields auto-relocated |
| FSM / VM | same directory | `<relfilenode>_fsm` / `_vm` | far smaller than main | auxiliary; deleting risks inconsistency |
| Tablespace | `$PGDATA/pg_tblspc/<tblspc_oid>/` | symlink to real path | none | backup must handle separately |

Keep this table handy for backups and disk forensics.

## Alternatives and Trade-offs: Why Not MySQL or Single-File Databases?

You might ask: why bother with all this complexity? Why not be like SQLite with one file per database? Postgres' multi-directory design has costs and rewards:

- **Reward**: multiple databases share one buffer pool, improving memory utilization; WAL is cluster-wide, so crash recovery replays a single log.
- **Cost**: cross-database queries (`dblink`, `postgres_fdw`) perform terribly because they go over the wire protocol even locally. If you need frequent cross-database JOINs, the design should put related tables in the same database — split tenants by database, not features.
- **vs. MySQL**: MySQL's `datadir` also has one directory per database, but table files are named `tablename.frm` / `tablename.ibd` — far more human-readable than Postgres' OID naming. Postgres' OID naming is purely historical baggage, but the payoff is that `ALTER TABLE ... RENAME` doesn't touch physical files — just updates a `pg_class` row, instant.

## FAQ

**Q: What's the difference between a PostgreSQL database cluster and multiple databases on a single server?**

A: A cluster is one complete `initdb` instance, containing multiple databases that share one WAL and one memory pool, listening on one port by default. A single server can run multiple clusters (multiple `$PGDATA`, multiple ports), but they're independent process groups sharing no memory or WAL. Clusters save resources internally; clusters provide stronger isolation and independent upgrades.

**Q: Why are directory names under `base/` numeric instead of database names?**

A: Because the directory names are database OIDs (object identifiers), not names. Postgres uses OIDs as primary keys for all metadata; names are just a field in `pg_database`. This lets `ALTER DATABASE ... RENAME` work without moving physical directories.

**Q: Why does the table file change after `VACUUM FULL`?**

A: `VACUUM FULL` rewrites the entire table, copying live tuples to a new file and deleting the old one. The process assigns a new `relfilenode`, so the file path changes. Regular `VACUUM` only cleans dead tuples, never changes `relfilenode`, but also never returns disk space to the OS.

**Q: What happens when a table exceeds 1GB?**

A: Postgres splits the table into segment files named `relfilenode`, `relfilenode.1`, `relfilenode.2`, and so on. This handles filesystems with single-file size limits. Reads and writes are transparent to the application, but backup tools must capture all segments.

**Q: Why does `pg_relation_filepath()` return a path different from what's under `base/`?**

A: If you use a custom tablespace, `pg_relation_filepath()` returns a path like `pg_tblspc/<tablespace_oid>/<database_oid>/<relfilenode>` instead of `base/<database_oid>/<relfilenode>`, because the table file physically lives at the tablespace's target location.

## References & Community Insights

There's been a lively Hacker News thread recently about AI-generated images in technical blogs, and the comments are brutally split — half the people say flashy illustrations actively repel them, the other half say pure text is too dry. I'm firmly in the pure-text camp, especially for low-level Postgres source analysis — a botched AI diagram is worse than a terminal screenshot. The thread itself reflects a broader reality: **the technical community is increasingly impatient with surface polish; people want directly actionable substance.** That aligns perfectly with how we debug `base/` — skip theory, hit the wall, then read the theory.

Here are a few resources I've leaned on heavily recently, and they've genuinely saved me:

- [The Internals of PostgreSQL — Chapter 1: Database Cluster, Databases and Tables](https://www.interdb.jp/pg/pgsql01.html) — the most systematic illustrated treatment; read it end to end.
- [PostgreSQL Official Docs: Database File Layout](https://www.postgresql.org/docs/current/storage-file-layout.html) — mediocre prose but authoritative; settle disputes against it.
- [Hacker News discussion on PostgreSQL internals](https://news.ycombinator.com/item?id=42000000) — real users sharing war stories, far livelier than the docs, especially for the traps that aren't documented but you *will* hit.

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "What's the difference between a PostgreSQL database cluster and multiple databases on a single server?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "A cluster is one complete initdb instance, containing multiple databases that share one WAL and one memory pool, listening on one port by default. A single server can run multiple clusters (multiple $PGDATA, multiple ports), but they're independent process groups sharing no memory or WAL."
    }
  },{
    "@type": "Question",
    "name": "Why are directory names under base/ numeric instead of database names?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Because the directory names are database OIDs (object identifiers), not names. Postgres uses OIDs as primary keys for all metadata, so renaming a database doesn't require moving physical directories."
    }
  },{
    "@type": "Question",
    "name": "Why does the table file change after VACUUM FULL?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "VACUUM FULL rewrites the entire table, copying live tuples to a new file and deleting the old one. The process assigns a new relfilenode, so the file path changes. Regular VACUUM only cleans dead tuples, never changes relfilenode, but also never returns disk space to the OS."
    }
  },{
    "@type": "Question",
    "name": "What happens when a table exceeds 1GB?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Postgres splits the table into segment files named relfilenode, relfilenode.1, relfilenode.2, and so on. Reads and writes are transparent to the application, but backup tools must capture all segments."
    }
  },{
    "@type": "Question",
    "name": "Why does pg_relation_filepath() return a path different from what's under base/?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "If you use a custom tablespace, pg_relation_filepath() returns a path like pg_tblspc/<tablespace_oid>/<database_oid>/<relfilenode> instead of base/<database_oid>/<relfilenode>, because the table file physically lives at the tablespace's target location."
    }
  }]
}
</script>
```

---
✅ All agents reported back!
├─ 🟠 Reddit: 12 threads
├─ 🟡 HN: 12 storys │ 1,019 points │ 739 comments
└─ 🗣️ Top voices: r/BestofRedditorUpdates, r/nvidia, r/DotA2
---

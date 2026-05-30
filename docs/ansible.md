# Ansible Integration

> **Status: planned.** This page documents the intended design for the Ansible collection. The collection modules have not been written yet.

`pyoe` is designed to be the Python backend for an Ansible collection. Each major operation maps cleanly to an Ansible module or lookup.

---

## Planned modules

| Module | Wraps | Description |
|---|---|---|
| `oe_db` | `create_empty_db` | Ensure an OpenEdge database exists |
| `oe_schema_sync` | `sync_schema` | Idempotent schema synchronisation |
| `oe_schema_dump` | `dump_schema` | Dump a database schema to a `.df` file |
| `oe_schema_facts` | `parse_df` | Read a `.df` file into Ansible facts |

### Planned lookups

| Lookup | Description |
|---|---|
| `oe_schema` | Return schema facts from a live database or a `.df` file |

---

## Design notes

### `oe_db` module (planned)

```yaml
- name: Ensure application database exists
  oe_db:
    path: /var/db/myapp
    state: present
    dlc: /usr/dlc
```

```yaml
- name: Remove a database
  oe_db:
    path: /var/db/old_tenant
    state: absent
```

### `oe_schema_sync` module (planned)

```yaml
- name: Apply schema version 2.3 to production database
  oe_schema_sync:
    db: /var/db/myapp
    schema: /schemas/app_v2.3.df
    dlc: /usr/dlc
  register: sync_result

- name: Show what changed
  debug:
    msg: "{{ sync_result.delta_bytes }} bytes applied"
  when: sync_result.changed
```

The module will be idempotent — running it twice with the same `.df` is safe and will report `changed: false` on the second run (because the delta will be empty).

### Multi-database pattern (planned)

```yaml
- name: Update all tenant databases
  oe_schema_sync:
    db: "{{ item }}"
    schema: /schemas/tenant_app.df
  loop: "{{ tenant_db_paths }}"
  async: 600
  poll: 0
  register: sync_jobs

- name: Wait for all syncs to complete
  async_status:
    jid: "{{ item.ansible_job_id }}"
  loop: "{{ sync_jobs.results }}"
  register: finished
  until: finished.finished
  retries: 60
  delay: 10
```

> Note: Ansible's `async` + `poll: 0` provides parallelism at the task level. For tighter Python-level threading, the `sync_many` function can be called directly from a custom action plugin.

---

## Implementation notes for collection authors

- All `pyoe` functions accept `dlc=` so the collection can expose it as a module parameter or read it from `ansible.cfg`.
- `OERuntimeError` exposes `.returncode` and `.stderr` for structured error reporting in module `fail_json`.
- `SyncResult` from `sync_many` maps directly to Ansible's `result` dict structure.
- `create_empty_db` is in a separate module (`pyoe.db`) so it can be imported without pulling in schema dependencies.

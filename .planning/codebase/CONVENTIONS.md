# Coding Conventions

**Analysis Date:** 2026-03-22

## Naming Patterns

**Files:**
- Task files: `main.yml` as primary entry point; subtask files in snake_case (e.g., `setup.yml`, `firewall.yml`, `swap.yml`)
- Default variables: `defaults/main.yml` — contains all role defaults and version pins
- Template files: `.j2` extension with snake_case names matching their output (e.g., `traefik.yml`, `docker-compose.yml.j2`)
- Handler files: `handlers/main.yml` for global handlers; role-specific handlers possible but rarely used
- Variable files: Config files are YAML, not separate `vars/` directories — variables defined in `defaults/main.yml` or inventory

**Directories:**
- Role folders: snake_case matching role name (e.g., `jellyfin`, `docker_proxy`, `traefik`)
- Template subdirectories: `templates/` flat structure (no nesting); nested folders only for complex configs (e.g., `roles/grafana/templates/provisioning/`)
- Subtask organization: Large roles split tasks into include files in same `tasks/` directory, included via `include_tasks`

**Variables:**
- Role defaults: lowercase with underscores (e.g., `jellyfin_version`, `docker_dir`, `docker_proxy_version`)
- Inventory variables: lowercase with underscores, host-scoped (e.g., `jellyfin_host`, `traefik_app_network_gateway`)
- Internal facts (set_fact): lowercase underscore prefix for scope (e.g., `crowdsecLapiKey`, `lapi_key_file` after register)
- Boolean variables: explicit `| bool` or `| default(false)` for safety (e.g., `system_swap_enabled | bool`)

**Functions/Tasks:**
- Task names: Sentence case, descriptive action (e.g., "Create traefik data directories", "Copy the traefik.yml", "Make sure the Jellyfin container is created and running")
- Handler names: Match the resource being restarted (e.g., "Restart jellyfin", "Restart crowdsec")
- Module names: Use fully qualified names with `ansible.builtin.*` or collection prefix (e.g., `ansible.builtin.file`, `community.docker.docker_container`, `ansible.posix.mount`)

**Types:**
- Container image versions: pinned in `defaults/main.yml` as `{{ service_version }}` variable
- Ports: always as strings in docker-compose labels (e.g., `port: "8096"`, `entrypoints: "https"`)
- File modes: always as strings in octal (e.g., `mode: "0755"`, `mode: "0640"`, `mode: "0600"`)

## Code Style

**Formatting:**
- YAML indentation: 2 spaces (enforced by `.yamllint`)
- Line length: unlimited (disabled in `.yamllint`)
- Truthy values: explicit `true` or `false` (or legacy `yes`/`no`), enforced by linter
- Comments: space after `#` required
- Braces: 0 spaces inside, max 1 space allowed (e.g., `{ key: value }`)
- Octal values: forbid implicit and explicit octal syntax

**Linting:**
- Tool: `ansible-lint` with config in `.ansible-lint`
- Excluded paths: `.git/`, `.github/`, `.ansible/roles/` (external roles not checked)
- Warnings enabled: `yaml`, `fqcn`, `var-naming[no-role-prefix]`, `command-instead-of-module`
- Warnings disabled: `var-naming[pattern]`, `command-instead-of-shell`, `name[template]`, `no-handler`
- Skip list: `experimental` rules

**Formatting Tool:**
- Linter: `yamllint` with config in `.yamllint`
- Extends: `default` preset
- Key enforcement: line-length disabled, truthy values strict, octal forbid implicit/explicit
- Comments indentation: disabled

## Import Organization

**Order (typical role structure):**
1. YAML document marker (`---`)
2. Task names (inline tasks) or include_tasks for sub-task files
3. Handlers import (in playbook only)
4. Roles list (in playbook)

**Include Pattern:**
- Subtasks included via `ansible.builtin.include_tasks` with descriptive task wrapper name
- Apply context passed for become and other modifiers (e.g., `apply: { become: true }`)
- Example:
  ```yaml
  - name: Configure swap
    ansible.builtin.include_tasks:
      file: swap.yml
      apply:
        become: true
    when: system_swap_enabled
  ```

**Path Aliases:**
- No path aliases used; all paths explicit
- Docker directory standardized: `{{ docker_dir }}` (defaults to `/opt/docker`)
- Storagebox path: `{{ storagebox_mount_path }}` (defaults to `/mnt/storagebox`)
- User/group: `{{ username }}` for file ownership

## Error Handling

**Patterns:**

**Command Execution Control:**
- `changed_when: false` — used when command queries state (e.g., `stat`, `command`, `docker exec` checks) and shouldn't mark as changed
- `changed_when: true` — used when command makes a change and Ansible can't detect it automatically (e.g., `restic init`, custom setup commands)
- `failed_when: false` — allows command to "fail" without halting playbook, used for optional checks (e.g., crowdsec password file checks, ntfy token checks)

**Examples:**
```yaml
# Read operation - never marks as changed
- name: Check if restic repo is initialized
  ansible.builtin.command: restic snapshots
  register: restic_repo_check
  failed_when: false
  changed_when: false

# Optional check - proceed even if fails
- name: Read crowdsecLapiKey from server
  ansible.builtin.slurp:
    src: "{{ docker_dir }}/crowdsec/.traefik-bouncer-key"
  register: lapi_key_file
  when: crowdsecLapiKey is not defined

# Explicit change declaration
- name: Initialize restic repo
  ansible.builtin.command: restic init
  when: restic_repo_check.rc != 0
  changed_when: true
```

**Retry/Delay Pattern:**
- `retries: N` combined with `until: condition` for waiting on async operations (e.g., waiting for container health checks, LAPI startup)
- `delay: 5` (5 seconds default) between retries
- Example:
  ```yaml
  - name: Wait for CrowdSec LAPI to be ready
    ansible.builtin.command: docker exec crowdsec cscli bouncers list -o json
    register: bouncers_result
    retries: 15
    delay: 5
    until: bouncers_result.rc == 0
    changed_when: false
  ```

**Conditional Execution:**
- `when:` statements are explicit and descriptive
- Use variable checks with `| default(false)` or `| bool` for safety
- Multi-line when clauses use list syntax (not strings)
- Examples:
  ```yaml
  when: jellyfin_storage_box_mount_enabled | default(false)

  when:
    - restic_backup_enabled | bool
    - restic_repo_check.rc != 0
  ```

**Register and Fact Setting:**
- `register: variable_name` follows Ansible naming (lowercase with underscores)
- Used to store command output for conditional checks or passing to subsequent tasks
- `ansible.builtin.set_fact` converts registers into playbook-level facts for use across roles
- Example:
  ```yaml
  - name: Read crowdsecLapiKey from server
    ansible.builtin.slurp:
      src: "{{ docker_dir }}/crowdsec/.traefik-bouncer-key"
    register: lapi_key_file
    when: crowdsecLapiKey is not defined

  - name: Set crowdsecLapiKey fact for this run
    ansible.builtin.set_fact:
      crowdsecLapiKey: "{{ lapi_key_file.content | b64decode | trim }}"
    when: crowdsecLapiKey is not defined
  ```

## Logging

**Framework:** No explicit logging framework; Ansible's built-in output used

**Patterns:**
- Task names serve as log entries — verbose names explain what's happening (e.g., "Copy the traefik.yml" vs just "Copy traefik")
- Handler notifications provide visibility into service restarts (notify lines documented clearly)
- Command output captured via `register` for conditional checks and debugging
- No custom logger integration; rely on Ansible's YAML callback output

## Comments

**When to Comment:**
- Configuration files (templates, Jinja2): Explain non-obvious settings (e.g., why certain Cloudflare IPs are trusted)
- Disabled or deprecated tasks: Always comment explaining why (e.g., `# media_cleanup disabled — rclone sync from seedbox would re-copy deleted files`)
- Complex conditionals or loops: Explain the intent if not obvious from task name
- External resource management: Note where files are created/stored (e.g., `# Exclude paths already on storagebox`)

**JSDoc/TSDoc:**
- Not used (YAML/Ansible context, no code generation)
- Comments are single-line with `#` prefix

**Example Comments:**
```yaml
# Retention policy
restic_keep_daily: 7
restic_keep_weekly: 4
restic_keep_monthly: 3

# Exclude paths already on storagebox
restic_exclude_paths:
  - "{{ docker_dir }}/immich/external"
  - "{{ docker_dir }}/jellyfin/media"

# media_cleanup disabled — rclone sync from seedbox would re-copy deleted files
# - role: media_cleanup
#   tags:
#     - media_cleanup
```

## Function Design

**Size:**
- Task files: split into subtasks via `include_tasks` when file exceeds ~100 lines (e.g., `system/tasks/` has `main.yml`, `setup.yml`, `swap.yml`, `firewall.yml`)
- Docker container tasks: typically 1-2 tasks per role for container creation + config setup
- No function-level abstractions; Ansible is declarative

**Parameters:**
- Container creation uses structured labels for Traefik config (no bash parameter passing)
- Variable passing via `defaults/main.yml` or inventory, never inline arguments
- `loop:` used for repeating tasks over lists (directories, items, etc.)

**Return Values:**
- Commands register output for checking return codes (`rc` field)
- Task names logged; no explicit return statements needed

## Module Design

**Exports:**
- Roles are self-contained; no explicit exports beyond handlers (which are global)
- Variables exposed via `defaults/main.yml` — all role configuration defined there
- Facts set via `ansible.builtin.set_fact` are playbook-global after assignment

**Barrel Files:**
- Not applicable (Ansible roles don't have index/barrel patterns)
- Handler imports in playbook are the closest analogue: `handlers/main.yml` imported once globally

**Role Execution Model:**
- Roles execute in order defined in `playbook.yml`
- Tags allow selective execution (e.g., `--tags "traefik"`)
- Handler notifications queued during role execution and flushed at end of play
- No inter-role dependencies enforced via Ansible; order in playbook is the dependency mechanism

**Docker Label Conventions:**
- Every containerized service uses Traefik labels for HTTP routing
- Labels follow pattern: `traefik.http.routers.{{ service_name }}.rule: "Host(...)"`
- Network membership via `networks:` list in docker_container definition
- Example structure in `roles/jellyfin/tasks/main.yml`:
  ```yaml
  labels:
    traefik.enable: "true"
    traefik.docker.network: "app_network"
    traefik.http.routers.jellyfin.entrypoints: "https"
    traefik.http.routers.jellyfin.rule: "Host(`{{ jellyfin_host }}`)"
    traefik.http.routers.jellyfin.middlewares: "open-external@file"
    traefik.http.services.jellyfin.loadbalancer.server.port: "8096"
  ```

---

*Convention analysis: 2026-03-22*

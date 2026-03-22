# Testing Patterns

**Analysis Date:** 2026-03-22

## Test Framework

**Runner:**
- Primary: `ansible-lint` for linting and basic validation
- Secondary: Manual `--check` (dry-run) via CLI
- No automated unit test framework in use (Ansible lacks standard test harness for this playbook)
- External roles include Molecule tests (in `.ansible/roles/geerlingguy.docker/molecule/`, `.ansible/roles/geerlingguy.pip/molecule/`) but not integrated into main playbook CI

**Assertion Library:**
- None — Ansible conditional execution (`when:`, `failed_when:`, `changed_when:`) serves as assertions

**Run Commands:**
```bash
# Full playbook lint
ansible-lint playbook.yml

# YAML lint
yamllint .

# Dry-run a specific tag
ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml --vault-password-file ~/.vault_pass --check --tags "jellyfin"

# Full deployment
ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml --vault-password-file ~/.vault_pass
```

## Test File Organization

**Location:**
- No separate test files — tests are implicit in playbook execution
- Linting happens against role task files (`roles/*/tasks/*.yml`)
- External collection tests in `.ansible/collections/` are not part of primary test flow

**Naming:**
- Not applicable — playbook structure is the test structure

**Structure:**
- Test flow follows role execution order in `playbook.yml`
- Tags allow selective testing (e.g., `--tags "traefik"` runs only traefik role)
- Each role is a testable unit; execution order is the only dependency

## Test Structure

**Suite Organization:**
Ansible doesn't use traditional test suites. Instead, testing happens via:

1. **Linting Phase** — Static validation:
   ```bash
   ansible-lint playbook.yml
   yamllint .
   ```

2. **Dry-Run Phase** — Check mode validation:
   ```bash
   ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml \
     --vault-password-file ~/.vault_pass --check --tags "jellyfin"
   ```

3. **Execution Phase** — Full deployment with handler notifications and actual state changes

**Patterns:**
- Setup: None explicit — roles are self-contained; all setup in `defaults/main.yml` and role tasks
- Teardown: None explicit — handlers manage service restarts (notify pattern)
- Assertion: Conditional logic (`when:`, `failed_when:`, `until:`, `retries:`) validates expected state

**Example Conditional Assertion Pattern** (from `roles/backup/tasks/main.yml`):
```yaml
- name: Check if restic repo is initialized
  ansible.builtin.command: >
    restic -r {{ restic_repo_path }} -p /etc/restic-password snapshots
  register: restic_repo_check
  failed_when: false
  changed_when: false

- name: Initialize restic repo
  ansible.builtin.command: >
    restic -r {{ restic_repo_path }} -p /etc/restic-password init
  when:
    - restic_backup_enabled | bool
    - restic_repo_check.rc != 0
  changed_when: true
```

## Mocking

**Framework:**
- No mocking framework used
- External roles (geerlingguy.docker, geerlingguy.pip) include test fixtures but are not integrated

**Patterns:**
Ansible tests real infrastructure — no mocking. Testing approach:
- **Dry-run mode** (`--check`): Tests idempotency and task ordering without side effects
- **Register/fact checks**: Validate state before taking action (e.g., check restic repo exists before init)
- **Conditional execution**: Skip tasks if conditions not met, validate state via return codes

Example state check pattern:
```yaml
# From roles/crowdsec/tasks/main.yml
- name: Check if machine password file exists
  ansible.builtin.stat:
    path: "{{ docker_dir }}/crowdsec/.homepage-machine-password"
  register: machine_password_stat
  become: true

- name: Generate machine password
  ansible.builtin.command: openssl rand -base64 32
  register: generated_machine_password
  when: not machine_password_stat.stat.exists
  changed_when: true
```

**What to Mock:**
- Not applicable — infrastructure tests are integration-style
- External API calls: None mocked; real services used

**What NOT to Mock:**
- Docker daemon (community.docker.docker_container runs against real daemon)
- Filesystem operations (real directories created/managed)
- Command execution (actual commands run, return codes checked)
- Network configurations (real networks created, containers connected)

## Fixtures and Factories

**Test Data:**
- No fixtures or factories — configuration comes from `custom.yml` and `secret.yml`
- Version pins in `defaults/main.yml` act as test constants (e.g., `jellyfin_version: "latest"`)
- Example from `roles/jellyfin/defaults/main.yml`:
  ```yaml
  jellyfin_version: "latest"
  jellyfin_webhook_plugin_version: "18.0.0.0"
  jellyfin_webhook_plugin_url: "https://repo.jellyfin.org/releases/plugin/webhook/webhook_18.0.0.0.zip"
  ```

**Location:**
- Configuration: `custom.yml` (gitignored, user-supplied), `.custom.yml` (template)
- Secrets: `secret.yml` (vault-encrypted, gitignored), `.secret.yml` (template)
- Defaults: `roles/*/defaults/main.yml`

## Coverage

**Requirements:**
- No coverage target enforced
- All roles linted, but coverage metrics not tracked

**View Coverage:**
```bash
# Ansible doesn't provide coverage reports
# Manual review: check all role tasks are exercised via tags
ansible-playbook playbook.yml --list-tags  # View all available tags
```

## Test Types

**Unit Tests:**
- Not implemented; Ansible is imperative and role-focused
- Closest analogue: Individual role execution with `--tags`
  ```bash
  ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml \
    --vault-password-file ~/.vault_pass --tags "jellyfin"
  ```

**Integration Tests:**
- All tests are integration-style — roles test against real Docker daemon, filesystem, networks
- Role execution order in `playbook.yml` defines integration sequence
- Example integration: `docker_network` role must run before `traefik` (network dependency)

**E2E Tests:**
- Not automated; manual post-deployment validation:
  - Navigate to service URLs to verify Traefik routing works
  - Check Docker logs via dozzle role (`roles/dozzle/`)
  - Check uptime monitoring via gatus role (`roles/gatus/`)
  - Verify backup job runs via cron/systemd timer logs

## Common Patterns

**Async Testing:**
- `retries:` + `until:` pattern for waiting on async operations
- Example from `roles/crowdsec/tasks/main.yml`:
  ```yaml
  - name: Wait for CrowdSec LAPI to be ready
    ansible.builtin.command:
      cmd: docker exec crowdsec cscli bouncers list -o json
    register: bouncers_result
    retries: 15
    delay: 5
    until: bouncers_result.rc == 0
    changed_when: false
  ```

- Health check polling via `healthcheck:` in docker_container definition:
  ```yaml
  healthcheck:
    test: ["CMD", "cscli", "version"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 15s
  ```

**Error Testing:**
- Conditional task execution based on command return code
- Example from `roles/backup/tasks/main.yml`:
  ```yaml
  - name: Check if restic repo is initialized
    ansible.builtin.command: >
      restic -r {{ restic_repo_path }} -p /etc/restic-password snapshots
    register: restic_repo_check
    failed_when: false
    changed_when: false

  - name: Initialize restic repo
    ansible.builtin.command: >
      restic -r {{ restic_repo_path }} -p /etc/restic-password init
    when:
      - restic_backup_enabled | bool
      - restic_repo_check.rc != 0
    changed_when: true
  ```

**State Validation Pattern:**
Testing for file existence and conditional creation:
```yaml
# From roles/crowdsec/tasks/main.yml
- name: Check if machine password file exists
  ansible.builtin.stat:
    path: "{{ docker_dir }}/crowdsec/.homepage-machine-password"
  register: machine_password_stat
  become: true

- name: Generate machine password
  ansible.builtin.command: openssl rand -base64 32
  register: generated_machine_password
  when: not machine_password_stat.stat.exists
  changed_when: true
```

**Container Readiness Testing:**
All containerized roles use docker health checks or explicit `until:` loops:
```yaml
# Health check in docker_container
healthcheck:
  test: ["CMD", "cscli", "version"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 15s
```

---

*Testing analysis: 2026-03-22*

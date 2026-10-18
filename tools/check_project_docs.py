"""Validate the project planning contract using only the Python standard library."""

import argparse
from collections import Counter
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


STATUSES = ('todo', 'in_progress', 'blocked', 'done')
CURATED = ('README.md', 'AGENTS.md', 'docs/FSD.md', 'docs/AGENT_WORKFLOW.md',
           'docs/VALIDATION.md', 'docs/UPSTREAM.md', 'milestones/README.md')
TASK = re.compile(r'^### (M\d+\.\d+) - (.+)$', re.MULTILINE)


def without_code(text):
    return re.sub(r'^(`{3,}|~{3,}).*?^\1\s*$', '', text,
                  flags=re.MULTILINE | re.DOTALL)


def validate(root):
    """Return (errors, tasks, ready); paths are resolved relative to root."""
    root = Path(root).resolve()
    errors, tasks = [], {}
    documents = {root / name for name in CURATED}
    for folder in ('milestones', 'adr', 'evidence'):
        documents.update((root / folder).rglob('*.md'))
    contents = {}
    for path in sorted(documents):
        if not path.is_file():
            errors.append(f'Missing document: {path.relative_to(root)}')
            continue
        contents[path] = without_code(path.read_text(encoding='utf-8-sig'))
    requirements = set(re.findall(r'^### (FSD-\d+)\b',
                                 contents.get(root / 'docs/FSD.md', ''), re.MULTILINE))
    ledger = contents.get(root / 'milestones/README.md', '')
    for match in TASK.finditer(ledger):
        task_id = match[1]
        remainder = ledger[match.end():]
        section_end = re.search(r'^#{1,3} ', remainder, re.MULTILINE)
        body = remainder[:section_end.start()] if section_end else remainder
        fields = {}
        for name in ('Status', 'Depends', 'Size', 'Requirement', 'Evidence', 'Acceptance',
                     'Owner', 'Next', 'Blocker'):
            values = re.findall(r'^- ' + name + r':[ \t]*(.*)$', body, re.MULTILINE)
            if len(values) != 1 or not values[0].strip():
                errors.append(f'{task_id}: requires exactly one nonempty {name} field')
            fields[name] = values[0].strip() if values else ''
        if task_id in tasks:
            errors.append(f'Duplicate task ID: {task_id}')
            continue
        fields['dependencies'] = ([] if fields['Depends'] == 'none' else
                                  [item.strip() for item in fields['Depends'].split(',')])
        tasks[task_id] = fields
        if fields['Status'] not in STATUSES:
            errors.append(f'{task_id}: invalid status {fields["Status"]!r}')
        if fields['Status'] == 'in_progress' and fields['Owner'].casefold() == 'unassigned':
            errors.append(f'{task_id}: in_progress requires an assigned Owner')
        if fields['Status'] == 'blocked' and fields['Blocker'].casefold() == 'none':
            errors.append(f'{task_id}: blocked requires a concrete Blocker')
        if fields['Size'] not in ('1', '2', '3', '5', '8'):
            errors.append(f'{task_id}: invalid effort size {fields["Size"]!r}')
        for requirement in fields['Requirement'].split(','):
            if requirement.strip() not in requirements:
                errors.append(f'{task_id}: unknown requirement {requirement.strip()!r}')
        evidence = fields['Evidence']
        if fields['Status'] == 'done' and evidence == 'none':
            errors.append(f'{task_id}: done requires evidence')
        if evidence and evidence != 'none':
            path = (root / evidence).resolve()
            if (Path(evidence).is_absolute() or not path.is_relative_to(root)
                    or path.suffix.lower() != '.md' or not path.is_file()):
                errors.append(f'{task_id}: evidence must be an existing repository-relative .md file: {evidence}')
    if not tasks:
        errors.append('No tasks found in milestones/README.md')
    for task_id, fields in tasks.items():
        for dependency in fields['dependencies']:
            if dependency not in tasks:
                errors.append(f'{task_id}: unknown dependency {dependency!r}')
            elif fields['Status'] in ('done', 'in_progress') and tasks[dependency]['Status'] != 'done':
                errors.append(f'{task_id}: {fields["Status"]} requires completed dependency {dependency}')
    visiting, visited = set(), set()

    def visit(task_id):
        if task_id in visiting:
            errors.append(f'Dependency cycle involving {task_id}')
            return
        if task_id in visited or task_id not in tasks:
            return
        visiting.add(task_id)
        for dependency in tasks[task_id]['dependencies']:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)
    for path, content in contents.items():
        # Inline/image links and reference-link definitions. Optional link titles
        # are excluded; angle brackets permit destinations containing spaces.
        targets = re.findall(r'!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)', content)
        targets += re.findall(r'^\s*\[[^\]\n]+\]:\s*(<[^>]+>|\S+)', content, re.MULTILINE)
        for target in targets:
            target = target.strip('<>')
            if target.startswith('#') or urlsplit(target).scheme or target.startswith('//'):
                continue
            destination = unquote(target.split('#', 1)[0].split('?', 1)[0])
            if destination and not (path.parent / destination).exists():
                errors.append(f'{path.relative_to(root)}: broken local link {target!r}')
    ready = [task_id for task_id, fields in tasks.items()
             if fields['Status'] == 'todo' and all(
                 dependency in tasks and tasks[dependency]['Status'] == 'done'
                 for dependency in fields['dependencies'])]
    return errors, tasks, ready


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    errors, tasks, ready = validate(args.root)
    counts = Counter(task['Status'] for task in tasks.values())
    print('Tasks: ' + ', '.join(f'{status}={counts[status]}' for status in STATUSES))
    effort = sum(int(task['Size']) for task in tasks.values() if task['Size'] in ('1', '2', '3', '5', '8'))
    print(f'Total relative effort: {effort} (not a time estimate)')
    done_effort = sum(int(task['Size']) for task in tasks.values()
                      if task['Status'] == 'done' and task['Size'] in ('1', '2', '3', '5', '8'))
    print(f'Closed scope effort: {done_effort}/{effort} (not feasibility or capability confidence)')
    milestones = sorted({task_id.split('.')[0] for task_id in tasks}, key=lambda name: int(name[1:]))
    for milestone in milestones:
        members = [task for task_id, task in tasks.items() if task_id.split('.')[0] == milestone]
        total = sum(int(task['Size']) for task in members if task['Size'] in ('1', '2', '3', '5', '8'))
        closed = sum(int(task['Size']) for task in members
                     if task['Status'] == 'done' and task['Size'] in ('1', '2', '3', '5', '8'))
        print(f'{milestone}: tasks={len(members)}, effort={total}, closed scope effort={closed}/{total}')
    print('Ready tasks: ' + (', '.join(ready) or 'none'))
    for error in errors:
        print(f'ERROR: {error}')
    print(f'Document validation: {"FAILED" if errors else "PASSED"}')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())

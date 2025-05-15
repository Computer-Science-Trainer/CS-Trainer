
from fastapi import APIRouter
from database import execute

router = APIRouter()


def collect_leaf_labels(topics, parent_id):
    children = [t for t in topics if t['parent_id'] == parent_id]
    if not children:
        parent = next((t for t in topics if t['id'] == parent_id), None)
        return [parent['label']] if parent else []
    leafs = []
    for child in children:
        leafs.extend(collect_leaf_labels(topics, child['id']))
    return leafs


def build_tree(topics, parent_id):
    children = [t for t in topics if t['parent_id'] == parent_id]
    result = []
    for child in children:
        grandchildren = [t for t in topics if t['parent_id'] == child['id']]
        if grandchildren:
            result.append({
                "label": child['label'],
                "accordions": build_tree(topics, child['id'])
            })
        else:
            result.append(child['label'])
    return result


@router.get('/topics')
def get_topics():
    rows = execute("SELECT id, label, code, section, parent_id FROM topics")
    topics = [dict(zip(['id', 'label', 'code', 'section', 'parent_id'], row))
              for row in rows]
    section_map = {}
    for t in topics:
        section = t['section']
        if section not in section_map:
            section_map[section] = []
        section_map[section].append(t)
    result = []
    for section, items in section_map.items():
        accordions = build_tree(items, None)
        result.append({
            "label": section,
            "accordions": accordions
        })
    return result

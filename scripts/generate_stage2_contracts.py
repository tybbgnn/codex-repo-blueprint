"""Generate author guidance, depth contract and S2/S3 contracts from stage-io."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate(root=ROOT):
    source = json.loads((root / 'references/stage-io.json').read_text())
    stages = source['stages']
    stage = stages['S2']
    schema = stage['ledger_schema']
    canonical = dict(source['canonical_schema_header'], stages={})
    for key, definition in stages.items():
        contract = dict(definition.get('runtime_contract', {}), version=source['version'],
                        stage=int(key[1:]), builder=definition['builder'])
        if 'external_inputs' in definition:contract['external_inputs']=definition['external_inputs']
        contract['inputs'] = {row['file']: dict(required=not row.get('optional',False),
            **{field:row[field] for field in ('schema','format') if field in row})
            for row in definition['inputs'] if row['root']=='inputs'}
        contract['prerequisites'] = [row['file'] for row in definition['inputs'] if row['root']=='work']
        contract['outputs'] = {row['file']:row.get('schema', {'description':'See stage-io key_fields', 'type':['object','array','string','number','boolean','null']})
                               for row in definition['outputs'] if row['root']=='work'}
        contract['required_outputs'] = [row['file'] for row in definition['outputs'] if row['root']=='work'
                                       and not row.get('optional') and not any(c in row['file'] for c in '*<')]
        if key=='S2':
            contract['ownership'] = definition['ownership']
            contract['inputs']['ledgers/stage2.json']['schema'] = schema
        (root/'references/contracts'/f'{key}.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
        canonical['stages'][key] = {row['file']:row['schema'] for row in definition['outputs']
                                    if row['root']=='work' and 'schema' in row}
    for name,value in [('references/ledger-schema.json',schema),
                       ('references/canonical-schema.json',canonical),
                       ('references/layer-contract.json',source['layer_contract'])]:
        (root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    layers = source['layer_contract']
    lines = ['# Depth 层级合同（生成文件）', '', '唯一来源：stage-io.json；生成器：scripts/generate_stage2_contracts.py。', '',
             '## 层级', '', '|depth|名称|ID 形式|来源|', '|---|---|---|---|']
    lines += [f"|{r['depth']}|{r['name']}|{r['id_scheme']}|{r['producer']}|" for r in layers['layers']]
    lines += ['', '## 渲染投影', '', layers['render_projection']]
    (root / 'references/layer-contract.md').write_text('\n'.join(lines) + '\n')
    policy = stage['ownership']['reading_group_policy']
    lines = ['# S2 作者判定步骤（生成文件）', '', '唯一来源：stage-io.json 的 reading_group_policy；开始编写任何新账本前逐项执行。', '']
    lines += [f'{i}. {step}' for i, step in enumerate(policy['authoring_steps'], 1)]
    lines += ['', '## 证据字段要求', '']
    lines += [f'- **{name}**：{detail}' for name, detail in policy['authoring_evidence_fields'].items()]
    lines += ['', policy.get('information_preservation','').rstrip()]
    (root / 'references/s2-authoring.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    generate()

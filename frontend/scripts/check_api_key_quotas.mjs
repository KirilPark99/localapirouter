import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import vm from 'node:vm';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { createServer } = await import(path.join(root, 'node_modules/vite/dist/node/index.js'));
const scratch = fs.mkdtempSync(path.join(process.env.TMPDIR || os.tmpdir(), 'quota-ui-check-'));
let language = 'ru', fetches = 0;
globalThis.localStorage = { getItem: key => key === 'myairouter_lang' ? language : null };
globalThis.fetch = () => { fetches++; throw new Error('No network allowed'); };
const rules = [
  { id: 'a'.repeat(32), enabled: true, scope: 'model', model: 'fixture/model', period: 'day', requests: 4, tokens: 1000, usd: 1 },
  { enabled: true, scope: 'profile', model: 'route/test', period: 'custom', duration_seconds: 90, anchor: '2026-10-08T00:00:00Z', requests: 2 },
  { enabled: false, scope: 'key', period: 'interval', start: '2026-10-08T00:00:00Z', end: '2026-10-09T00:00:00Z', tokens: 500 },
];
const key = { id: 17, name: 'Fixture', key_prefix: 'fixture', masked_key: 'fixture', enabled: true, permissions: ['direct', 'custom'], total_requests: 1, quota_rules: rules };
const usage = [{ rule_id: rules[0].id, active: true, start: '2026-10-08T00:00:00Z', end: '2026-10-09T00:00:00Z', used: { requests: 1, tokens: 30, usd: 0.00005 }, remaining: { requests: 3, tokens: 970, usd: 0.99995 } }];
let empty = false;
const server = await createServer({ root, configFile: false, cacheDir: scratch, server: { middlewareMode: true }, plugins: [{
  name: 'quota-regression-state', enforce: 'pre', transform(code, id) {
    if (!id.endsWith('/pages/ApiKeysPage.tsx')) return;
    const replace = (anchor, value) => { assert.ok(code.includes(anchor), anchor); code = code.replace(anchor, value); };
    replace('useState<RouterApiKey[]>([])', `useState<RouterApiKey[]>(${JSON.stringify([{ ...key, quota_rules: empty ? [] : rules }])})`);
    replace('const [isModalOpen, setIsModalOpen] = useState(false);', 'const [isModalOpen, setIsModalOpen] = useState(true);');
    replace('useState<RouterApiKey | null>(null)', `useState<RouterApiKey | null>(${JSON.stringify(key)})`);
    replace('useState<PeriodQuotaRule[]>([])', `useState<PeriodQuotaRule[]>(${JSON.stringify(empty ? [] : rules)})`);
    replace('useState<PeriodQuotaUsage[]>([])', `useState<PeriodQuotaUsage[]>(${JSON.stringify(usage)})`);
    return code;
  },
}] });
try {
  const { ApiKeysPage } = await server.ssrLoadModule('/src/pages/ApiKeysPage.tsx');
  const { I18nProvider } = await server.ssrLoadModule('/src/i18n/context.tsx');
  const render = () => renderToStaticMarkup(React.createElement(I18nProvider, null, React.createElement(ApiKeysPage)));
  let html = render();
  assert.ok(html.includes('Лимиты запросов, токенов и расходов'), 'Russian quota section must be visible');
  assert.ok(html.indexOf('aria-label="Period quotas"') < html.indexOf('name="key-name"'), 'Quotas must precede secondary fields');
  for (const label of ['Добавить лимит', 'Запросы', 'Токены', 'USD', 'Своя длительность', 'Интервал дат', 'Израсходовано', 'Осталось']) assert.ok(html.includes(label), label);
  assert.equal((html.match(/aria-label="Quota \d (requests|tokens|usd)"/g) || []).length, 9);
  assert.ok(html.includes('list="quota-model-options"'), 'Native model catalog picker');
  assert.ok(html.includes('fixture/model') && html.includes('1000') && html.includes('$1'), 'Table shows limits, not just count');
  language = 'en'; html = render();
  assert.ok(html.includes('Request, token and spending limits'));
  language = 'de'; html = render();
  assert.ok(html.includes('Request, token and spending limits'), 'Other locales fall back safely');
  empty = true;
  await server.moduleGraph.invalidateAll();
  const { ApiKeysPage: EmptyPage } = await server.ssrLoadModule('/src/pages/ApiKeysPage.tsx');
  const { I18nProvider: FreshI18nProvider } = await server.ssrLoadModule('/src/i18n/context.tsx');
  language = 'ru';
  html = renderToStaticMarkup(React.createElement(FreshI18nProvider, null, React.createElement(EmptyPage)));
  assert.ok(html.includes('Добавить лимит') && html.includes('Без периодических лимитов'));
  assert.equal(fetches, 0);
  console.log('PASS: RU/EN/fallback, quota-first layout, empty state, all limits/windows, usage and table summary; zero network.');
} finally {
  await server.close();
  fs.rmSync(scratch, { recursive: true, force: true });
}

const ts=require('typescript');
const source=fs.readFileSync(root+'/src/pages/ApiKeysPage.tsx','utf8');
const ast=ts.createSourceFile('ApiKeysPage.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
const names=new Set(['openCreateModal','loadQuotaUsage','openEditModal','handleCreate','loadKeys']);
const snippets=[];
function visit(node){if(ts.isVariableStatement(node)){for(const d of node.declarationList.declarations){if(names.has(d.name.getText(ast))){snippets.push('var '+d.getText(ast)+';');names.delete(d.name.getText(ast));}}}ts.forEachChild(node,visit);}
visit(ast);assert.equal(names.size,0);
// The same production change handler now lives in the shared editor.
const editorSource=fs.readFileSync(root+'/src/components/QuotaEditor.tsx','utf8');
const editorAst=ts.createSourceFile('QuotaEditor.tsx',editorSource,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
let changeFound=false;
function visitEditor(node){if(ts.isVariableDeclaration(node)&&node.name.getText(editorAst)==='changeQuota'){snippets.push('var '+node.getText(editorAst)+';');changeFound=true;}ts.forEachChild(node,visitEditor);}
visitEditor(editorAst);assert.ok(changeFound);
const fixture={id:17,name:'Offline quota key',permissions:['direct','routes','judge','custom'],allowed_models:['fixture/model'],rate_limit_rpm:5,notes:'note',quota_rules:[{id:'a'.repeat(32),enabled:true,scope:'model',model:'fixture/model',period:'day',requests:4,tokens:1000,usd:1}]};
let stored=structuredClone(fixture), calls=[],alerts=[];
const state={console,JSON,Number,formQuotas:[],quotaUsage:[],usageError:'',saving:false,editingKey:null,formName:'',formDirect:true,formRoutes:true,formFusion:true,formJudge:true,formRpm:'',formNotes:'',keys:[],loading:false,isModalOpen:false,createdKeyData:null,alert:m=>alerts.push(m)};
for(const name of Object.keys(state)){state['set'+name[0].toUpperCase()+name.slice(1)]=v=>{state[name]=typeof v==='function'?v(state[name]):v;};}
state.apiRequest=async(path,options={})=>{
 calls.push({path,method:options.method||'GET',body:options.body?JSON.parse(options.body):undefined});
 if(path.endsWith('/usage'))return stored.quota_rules.map(r=>({rule_id:r.id,used:{requests:1,tokens:30,usd:.00005}}));
 if(options.method==='PUT'){const data=JSON.parse(options.body);stored={...stored,...data};return structuredClone(stored);}
 if(options.method==='POST'){stored={...JSON.parse(options.body),id:18,raw_api_key:'synthetic'};return structuredClone(stored);}
 return [structuredClone(stored)];
};
vm.createContext(state);
vm.runInContext(ts.transpileModule(snippets.join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText,state);
state.openEditModal(structuredClone(fixture));
await new Promise(resolve=>setImmediate(resolve));
assert.equal(state.formName,fixture.name);assert.equal(state.formJudge,true);assert.equal(state.formFusion,false);assert.equal(state.quotaUsage[0].rule_id,fixture.quota_rules[0].id);
state.changeQuota(0,{requests:9,usd:.25,enabled:false});
assert.equal(fixture.quota_rules[0].requests,4,'editing must not mutate loaded key');
await state.handleCreate({preventDefault(){}});
await new Promise(resolve=>setImmediate(resolve));
const put=calls.find(c=>c.method==='PUT');
assert.equal(put.path,'/api/admin/keys/17');
assert.equal(put.body.quota_rules[0].requests,9);assert.equal(put.body.quota_rules[0].usd,.25);assert.equal(put.body.quota_rules[0].enabled,false);assert.equal(put.body.quota_rules[0].id,fixture.quota_rules[0].id);
assert.equal('allowed_models' in put.body,false,'edit must preserve restrictions');
assert.deepEqual(Array.from(put.body.permissions),['custom','direct','routes','judge']);
assert.equal(stored.allowed_models[0],'fixture/model');assert.equal(state.keys[0].quota_rules[0].requests,9);assert.equal(state.saving,false);assert.equal(state.isModalOpen,false);
state.openCreateModal();assert.equal(state.editingKey,null);assert.equal(state.formQuotas.length,0);
state.formName='Created fixture';state.formQuotas=[{enabled:true,scope:'key',period:'custom',duration_seconds:60,anchor:'2026-10-08T00:00:00Z',requests:3}];
await state.handleCreate({preventDefault(){}});
assert.equal(calls.find(c=>c.method==='POST').body.quota_rules[0].anchor,'2026-10-08T00:00:00Z');assert.equal(state.createdKeyData.id,18);assert.equal(alerts.length,0);
state.openEditModal(structuredClone(fixture));
state.apiRequest=async()=>{throw new Error('synthetic save rejection');};
await state.handleCreate({preventDefault(){}});
assert.equal(alerts.at(-1),'synthetic save rejection');assert.equal(state.saving,false);assert.equal(state.isModalOpen,true);
console.log('PASS: create/edit/error handlers, quota payload/readback, identity and restrictions preserved; zero network.');


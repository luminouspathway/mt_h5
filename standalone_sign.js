const fs = require('fs');
const path = require('path');
const vm = require('vm');

// 独立签名脚本：加载 H5guard，注入浏览器 dfpId，单次 sign 输出 mtgsig
const h5path = path.join(__dirname, 'H5guard.js');
const code = fs.readFileSync(h5path, 'utf8').replace(/\r\n/g, '\n');

// 从环境读取参数（Python 传入）
const SIGN_URL = process.env.SIGN_URL || '';
const SIGN_DATA = process.env.SIGN_DATA || '';
const DFPID = process.env.DFPID || '';
const LOCALID = process.env.LOCALID || '';
const DFP_TS = process.env.DFP_TS || '';

const sandbox = {};
sandbox.window = sandbox; sandbox.self = sandbox; sandbox.globalThis = sandbox; sandbox.global = sandbox;
sandbox.process = undefined; sandbox.Buffer = undefined; sandbox.require = undefined;
sandbox.console = console; sandbox.setTimeout = setTimeout; sandbox.clearTimeout = clearTimeout;
sandbox.setInterval = setInterval; sandbox.clearInterval = clearInterval;
sandbox.JSON = JSON; sandbox.Math = Math;
sandbox.navigator = { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36', platform: 'Win32', language: 'zh-CN', languages: ['zh-CN'], maxTouchPoints: 5 };
sandbox.document = { get cookie() { return 'WEBDFPID=' + DFPID + '-' + DFP_TS + '-' + LOCALID; }, set cookie(v) { }, readyState: 'complete', createElement: () => ({}), getElementById: () => null, getElementsByTagName: () => ({ length: 0 }), addEventListener: () => { }, documentElement: {}, head: {}, body: {} };
sandbox.location = { href: 'https://h5.waimai.meituan.com/', protocol: 'https:', host: 'h5.waimai.meituan.com', hostname: 'h5.waimai.meituan.com', origin: 'https://h5.waimai.meituan.com' };
sandbox.history = { length: 1 };
sandbox.screen = { width: 929, height: 965, colorDepth: 24 };
const store = {
  dfpId: DFPID,
  localId: LOCALID,
  dfp_timestamp: DFP_TS,
};
sandbox.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: (k) => { delete store[k]; },
  clear: () => { for (const k in store) delete store[k]; },
  key: (i) => Object.keys(store)[i] || null,
  get length() { return Object.keys(store).length; }
};
sandbox.sessionStorage = sandbox.localStorage;
sandbox.performance = { now: () => Date.now(), timing: {}, navigation: {} };
sandbox.crypto = { getRandomValues: (a) => a };
sandbox.innerWidth = 929; sandbox.innerHeight = 965;
sandbox.btoa = (s) => Buffer.from(s, 'binary').toString('base64');
sandbox.atob = (s) => Buffer.from(s, 'base64').toString('binary');
sandbox.getComputedStyle = () => ({});
sandbox.matchMedia = () => ({ matches: false });
sandbox.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 16);
sandbox.cancelAnimationFrame = clearTimeout;
sandbox.XMLHttpRequest = class { open() { } setRequestHeader() { } send() { } addEventListener() { } };
sandbox.fetch = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}), text: () => Promise.resolve(''), headers: new Headers() });
sandbox.WebSocket = class { };
sandbox.Event = class { };
sandbox.Node = function Node() { };
sandbox.Window = function Window() { };
sandbox.Navigator = function Navigator() { };
sandbox.HTMLElement = function HTMLElement() { };
sandbox.EventSource = class { };
sandbox.Worker = class { };
sandbox.URL = require('url').URL;
sandbox.URLSearchParams = require('url').URLSearchParams;

vm.createContext(sandbox);
try {
  vm.runInContext(code, sandbox, { filename: 'H5guard.js' });
  sandbox.H5guard.sign({
    url: SIGN_URL,
    method: 'POST',
    data: SIGN_DATA,
    headers: { 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' }
  }).then(r => {
    const mt = JSON.parse(r.headers.mtgsig);
    console.log('MTGSIG:' + r.headers.mtgsig);
    console.log('DEBUG a2=' + mt.a2 + ' a3=' + mt.a3 + ' a6len=' + mt.a6.length + ' a5len=' + mt.a5.length);
    process.exit(0);
  }).catch(e => { console.error('sign err:', e.message || e); process.exit(1); });
} catch (e) {
  console.error('LOAD ERROR:', e.message);
  process.exit(1);
}
setTimeout(() => { console.error('timeout'); process.exit(2); }, 30000);

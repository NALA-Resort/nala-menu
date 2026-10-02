// The top-level pieces of a shared script, for tests/reach.py.
//
// Reads one script on stdin and prints, as JSON, every top-level unit: a
// function, a var, or a statement. Each unit carries the names it declares,
// a fingerprint of its source, the names it refers to (identifiers, and any
// word in a string literal, since an onclick in a built string calls a
// function too), and whether it runs as the page loads: every statement does,
// and so does a var whose initialiser calls something outside a function body,
// as an IIFE does. A change that reaches one of those reaches every page.
//
// esprima is the parser targaryen already brings (tests/package-lock.json):
// a hand-made brace counter cannot read this file, whose regular expressions
// hold braces of their own.
const esprima = require(require('path').join(__dirname, 'node_modules', 'esprima'));
const crypto = require('crypto');

let src = '';
process.stdin.on('data', d => { src += d; });
process.stdin.on('end', () => {
  let ast;
  try { ast = esprima.parse(src, { range: true }); }
  catch (e) { console.log(JSON.stringify({ error: String(e.message || e) })); return; }

  function walk(node, visit, inFn) {
    if (!node || typeof node.type !== 'string') return;
    visit(node, inFn);
    const fn = inFn || node.type === 'FunctionExpression' || node.type === 'FunctionDeclaration';
    for (const k of Object.keys(node)) {
      if (k === 'range') continue;
      const v = node[k];
      if (Array.isArray(v)) v.forEach(c => walk(c, visit, fn));
      else if (v && typeof v.type === 'string') {
        // a property name and an object key are not references
        if ((node.type === 'MemberExpression' && k === 'property' && !node.computed) ||
            (node.type === 'Property' && k === 'key')) continue;
        walk(v, visit, fn);
      }
    }
  }

  const units = ast.body.map(n => {
    const text = src.slice(n.range[0], n.range[1]);
    const unit = {
      kind: n.type === 'FunctionDeclaration' ? 'function'
          : n.type === 'VariableDeclaration' ? 'var' : 'stmt',
      names: [],
      hash: crypto.createHash('sha1').update(text.replace(/\s+/g, ' ')).digest('hex'),
      refs: [],
      atLoad: n.type !== 'FunctionDeclaration' && n.type !== 'VariableDeclaration',
      head: text.slice(0, 60).replace(/\s+/g, ' ')
    };
    if (n.type === 'FunctionDeclaration') unit.names.push(n.id.name);
    if (n.type === 'VariableDeclaration') n.declarations.forEach(d => unit.names.push(d.id.name));
    const refs = new Set();
    walk(n, (x, inFn) => {
      if (x.type === 'Identifier') refs.add(x.name);
      if (x.type === 'Literal' && typeof x.value === 'string')
        (x.value.match(/[A-Za-z_$][\w$]*/g) || []).forEach(w => refs.add(w));
      if (unit.kind === 'var' && !inFn && (x.type === 'CallExpression' || x.type === 'NewExpression'))
        unit.atLoad = true;
    }, false);
    unit.names.forEach(nm => refs.delete(nm));
    unit.refs = Array.from(refs);
    return unit;
  });
  console.log(JSON.stringify({ units }));
});

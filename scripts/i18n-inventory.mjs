import ts from 'typescript';
import fs from 'node:fs';
const files=fs.readdirSync('app').filter(f=>/\.(tsx|ts)$/.test(f)&&!f.startsWith('i18n'));
const strings=new Map();
const add=(text,source)=>{text=text.replace(/\s+/g,' ').trim();if(!/[a-zA-Z]/.test(text))return;const row=strings.get(text)||{text,sources:[]};if(!row.sources.includes(source))row.sources.push(source);strings.set(text,row);};
for(const f of files){
 const sf=ts.createSourceFile(f,fs.readFileSync('app/'+f,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 function walk(n){
  if(ts.isJsxText(n))add(n.text,f+':jsx');
  if(ts.isStringLiteral(n)||ts.isNoSubstitutionTemplateLiteral(n)){
   const p=n.parent;
   if(!ts.isImportDeclaration(p)&&!ts.isImportSpecifier(p)&&!ts.isJsxAttribute(p)&&!/^(?:\.|\/|#|\*|--|\[)/.test(n.text)&&!/[{}]/.test(n.text)&&(/\s/.test(n.text)||/^[A-Z][A-Za-z&/+-]*$/.test(n.text)))add(n.text,f+':literal');
   if(ts.isJsxAttribute(p)&&['title','aria-label','placeholder','label','hint','eyebrow','description','subtitle','alt'].includes(p.name.text))add(n.text,f+':attribute');
  }
  if(ts.isTemplateExpression(n))add(n.head.text+n.templateSpans.map((s,i)=>`{${i}}`+s.literal.text).join(''),f+':template');
  ts.forEachChild(n,walk);
 }walk(sf);
}
fs.writeFileSync('tmp/i18n-inventory.json',JSON.stringify([...strings.values()],null,2));
console.log('Inventory:',strings.size,'strings');
console.log([...strings.keys()].map((s,i)=>`${i+1}\t${s}`).join('\n'));

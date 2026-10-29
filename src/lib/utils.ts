export function formatSize(size:number):string { if(size<1024) return `${size} B`; const u=['KB','MB','GB','TB'];let n=size/1024;let i=0;while(n>=1024&&i<u.length-1){n/=1024;i++;}return `${n>=10?n.toFixed(1):n.toFixed(2)} ${u[i]}`; }
export function formatDate(value:string):string { return new Date(value).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); }
export function formatTime(value:string):string {return new Date(value).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});}
export function uid(prefix='id'):string {return `${prefix}-${crypto.randomUUID()}`;}
export function txId():string {return `SIM-${crypto.randomUUID().slice(0,8).toUpperCase()}`;}
export function initials(name:string) {return name.split(' ').map(x=>x[0]||'').slice(0,2).join('').toUpperCase();}
export function getFileKind(fileName:string,mime:string):'pdf'|'image'|'doc'|'sheet'|'code'|'archive'|'other' {const ext=fileName.split('.').pop()?.toLowerCase();if(ext==='pdf')return'pdf';if(mime.startsWith('image/'))return'image';if(['doc','docx','rtf'].includes(ext||''))return'doc';if(['xls','xlsx','csv'].includes(ext||''))return'sheet';if(['ts','js','json','md','txt','py','html','css'].includes(ext||''))return'code';if(['zip','rar','7z'].includes(ext||''))return'archive';return'other';}
export const wait=(ms:number)=>new Promise<void>(r=>setTimeout(r,ms));

/** Browser-only blob storage. No uploads, encryption, or cloud transfers occur. */
const DB='vaultchain-demo-files-v1';
function openDB():Promise<IDBDatabase>{
  return new Promise((resolve,reject)=>{
    const req=indexedDB.open(DB,1);
    req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains('blobs')) req.result.createObjectStore('blobs');};
    req.onsuccess=()=>resolve(req.result);
    req.onerror=()=>reject(req.error ?? new Error('IndexedDB unavailable'));
  });
}
export async function saveBlob(id:string, blob:Blob):Promise<void>{
  const db=await openDB();
  try{await new Promise<void>((resolve,reject)=>{const tx=db.transaction('blobs','readwrite');tx.objectStore('blobs').put(blob,id);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}finally{db.close();}
}
export async function readBlob(id:string):Promise<Blob|undefined>{
  const db=await openDB();
  try{return await new Promise((resolve,reject)=>{const tx=db.transaction('blobs','readonly');const req=tx.objectStore('blobs').get(id);req.onsuccess=()=>resolve(req.result as Blob|undefined);req.onerror=()=>reject(req.error);});}finally{db.close();}
}
export async function deleteBlob(id:string):Promise<void>{
  const db=await openDB();
  try{await new Promise<void>((resolve,reject)=>{const tx=db.transaction('blobs','readwrite');tx.objectStore('blobs').delete(id);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);});}finally{db.close();}
}

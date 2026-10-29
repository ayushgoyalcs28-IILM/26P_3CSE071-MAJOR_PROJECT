import {createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode} from 'react';
import type {Activity, ActivityType, FileItem, Folder, Role, Share, StorageNode, VaultState} from '../types';
import {seedState} from '../data/seed';
import {uid,txId} from '../lib/utils';
import {deleteBlob,readBlob,saveBlob} from '../lib/filestore';

const STATE_KEY='vaultchain-demo-state-v2';
const SESSION_KEY='vaultchain-demo-role';
const MAX_BYTES=12*1024*1024;
const allowedEmail=(email:string)=>/^[^\s@]+@university\.edu$/i.test(email.trim());
function loadState():VaultState {try{const raw=localStorage.getItem(STATE_KEY);if(raw){const data=JSON.parse(raw) as VaultState;if(Array.isArray(data.files)&&Array.isArray(data.shares)&&Array.isArray(data.activities)&&Array.isArray(data.nodes)&&Array.isArray(data.folders))return data;}}catch{/* Reset malformed demo state. */}return seedState;}
const actor='Alex Morgan';
function makeActivity(type:ActivityType,title:string,detail:string,who=actor):Activity{return {id:uid('evt'),type,title,detail,createdAt:new Date().toISOString(),txId:txId(),actor:who};}

type VaultContextValue = {
 state:VaultState;role:Role|null;signIn:(role:Role)=>void;signOut:()=>void;resetDemo:()=>Promise<void>;
 notify:(message:string,kind?:'success'|'error'|'info')=>void;toast:{message:string,kind:'success'|'error'|'info',id:number}|null;dismissToast:()=>void;
 uploadFiles:(files:FileList|File[],folderId?:string|null)=>Promise<void>;createFolder:(name:string)=>boolean;renameFile:(id:string,name:string)=>void;moveFile:(id:string,folderId:string|null)=>void;toggleStar:(id:string)=>void;
 trashFile:(id:string)=>void;restoreFile:(id:string)=>void;deleteFile:(id:string)=>Promise<void>;downloadFile:(id:string)=>Promise<void>;
 shareFile:(id:string,email:string,permission:'view'|'download')=>boolean;revokeShare:(shareId:string)=>void;toggleNode:(id:string)=>void;
};
const Ctx=createContext<VaultContextValue|null>(null);
export function VaultProvider({children}:{children:ReactNode}){
 const [state,setState]=useState<VaultState>(loadState);
 const [role,setRole]=useState<Role|null>(()=>{const r=sessionStorage.getItem(SESSION_KEY);return r==='student'||r==='admin'?r:null;});
 const [toast,setToast]=useState<{message:string,kind:'success'|'error'|'info',id:number}|null>(null);
 const notify=useCallback((message:string,kind:'success'|'error'|'info'='success')=>setToast({message,kind,id:Date.now()}),[]);
 useEffect(()=>{try{localStorage.setItem(STATE_KEY,JSON.stringify(state));}catch{notify('Demo storage is full. Some changes may not persist.','error');}},[state,notify]);
 const signIn=useCallback((r:Role)=>{sessionStorage.setItem(SESSION_KEY,r);setRole(r);},[]);
 const signOut=useCallback(()=>{sessionStorage.removeItem(SESSION_KEY);setRole(null);},[]);
 const log=(type:ActivityType,title:string,detail:string,who?:string)=>makeActivity(type,title,detail,who);
 const uploadFiles=async (input:FileList|File[],folderId:string|null=null)=>{
   const incoming=Array.from(input);if(!incoming.length)return;
   const accepted:FileItem[]=[];const skipped:string[]=[];
   for(const file of incoming){
     if(file.size>MAX_BYTES){skipped.push(`${file.name} exceeds 12 MB`);continue;}
     const id=uid('file');
     try{await saveBlob(id,file);}catch{skipped.push(`${file.name} could not be stored`);continue;}
     const now=new Date().toISOString();accepted.push({id,name:file.name,size:file.size,mime:file.type||'application/octet-stream',folderId,starred:false,status:'active',createdAt:now,updatedAt:now,owner:actor,origin:'local',fragmentCount:5});
   }
   if(accepted.length){setState(s=>({...s,files:[...accepted,...s.files],activities:[...accepted.map(f=>log('UPLOAD','Document uploaded',`${f.name} added to your browser-local vault`)),...s.activities]}));notify(`${accepted.length} file${accepted.length>1?'s':''} added to your vault`);}
   if(skipped.length)notify(skipped.join('; '),'error');
 };
 const createFolder=(name:string):boolean=>{const clean=name.trim();if(!clean){notify('Enter a folder name','error');return false;}if(state.folders.some(f=>f.name.toLowerCase()===clean.toLowerCase())){notify('A folder with that name already exists','error');return false;}setState(s=>({...s,folders:[...s.folders,{id:uid('folder'),name:clean,createdAt:new Date().toISOString()}],activities:[log('FOLDER','Folder created',`${clean} added to workspace`),...s.activities]}));notify('Folder created');return true;};
 const renameFile=(id:string,name:string)=>{const clean=name.trim();if(!clean)return;setState(s=>({...s,files:s.files.map(f=>f.id===id?{...f,name:clean,updatedAt:new Date().toISOString()}:f),activities:[log('RENAME','Document renamed',`Document renamed to ${clean}`),...s.activities]}));notify('File renamed');};
 const moveFile=(id:string,folderId:string|null)=>{const file=state.files.find(f=>f.id===id);if(!file)return;setState(s=>({...s,files:s.files.map(f=>f.id===id?{...f,folderId,updatedAt:new Date().toISOString()}:f),activities:[log('MOVE','Document moved',`${file.name} moved to ${s.folders.find(f=>f.id===folderId)?.name||'My Files'}`),...s.activities]}));notify('File moved');};
 const toggleStar=(id:string)=>setState(s=>({...s,files:s.files.map(f=>f.id===id?{...f,starred:!f.starred}:f)}));
 const trashFile=(id:string)=>{const file=state.files.find(f=>f.id===id);if(!file)return;setState(s=>({...s,files:s.files.map(f=>f.id===id?{...f,status:'trashed' as const}:f),activities:[log('DELETE','Document moved to trash',`${file.name} moved to trash`),...s.activities]}));notify('File moved to trash');};
 const restoreFile=(id:string)=>{const file=state.files.find(f=>f.id===id);if(!file)return;setState(s=>({...s,files:s.files.map(f=>f.id===id?{...f,status:'active' as const}:f),activities:[log('RESTORE','Document restored',`${file.name} restored`),...s.activities]}));notify('File restored');};
 const deleteFile=async(id:string)=>{const file=state.files.find(f=>f.id===id);if(!file)return;try{if(file.origin==='local')await deleteBlob(id);}catch{notify('Could not delete local file bytes','error');return;}setState(s=>({...s,files:s.files.filter(f=>f.id!==id),shares:s.shares.filter(x=>x.fileId!==id),activities:[log('DELETE','Document removed',`${file.name} permanently removed from browser demo`),...s.activities]}));notify('File permanently removed');};
 const downloadFile=async(id:string)=>{const file=state.files.find(f=>f.id===id);if(!file)return;if(file.origin==='sample'){notify('Sample file: no file bytes are attached. Upload your own file to test downloads.','info');return;}try{const blob=await readBlob(id);if(!blob){notify('The browser-stored file could not be found','error');return;}const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=file.name;document.body.append(a);a.click();a.remove();window.setTimeout(()=>URL.revokeObjectURL(url),60_000);setState(s=>({...s,activities:[log('DOWNLOAD','Document downloaded',`${file.name} downloaded from your browser`),...s.activities]}));notify('Download started');}catch{notify('Download failed','error');}};
 const shareFile=(id:string,email:string,permission:'view'|'download'):boolean=>{const recipient=email.toLowerCase().trim();const file=state.files.find(f=>f.id===id);if(!file)return false;if(!allowedEmail(recipient)){notify('Use a demo institution email: name@university.edu','error');return false;}if(state.shares.some(s=>s.fileId===id&&s.recipient===recipient&&s.active)){notify('This recipient already has active access','error');return false;}setState(s=>({...s,shares:[{id:uid('share'),fileId:id,recipient,permission,createdAt:new Date().toISOString(),active:true},...s.shares],activities:[log('SHARE','Access granted',`${file.name} shared with ${recipient} (${permission})`),...s.activities]}));notify('Demo access granted — no email was sent');return true;};
 const revokeShare=(id:string)=>{const share=state.shares.find(s=>s.id===id);if(!share)return;const file=state.files.find(f=>f.id===share.fileId);setState(s=>({...s,shares:s.shares.map(x=>x.id===id?{...x,active:false}:x),activities:[log('REVOKE','Access revoked',`${share.recipient} removed from ${file?.name||'document'}`),...s.activities]}));notify('Demo access revoked');};
 const toggleNode=(id:string)=>{if(role!=='admin'){notify('Administrator demo role required','error');return;}const node=state.nodes.find(n=>n.id===id);if(!node)return;const next:StorageNode['status']=node.status==='online'?'maintenance':'online';setState(s=>({...s,nodes:s.nodes.map(n=>n.id===id?{...n,status:next}:n),activities:[log('ADMIN','Storage node status updated',`${node.name} set to ${next} (simulation)`,'Demo administrator'),...s.activities]}));notify(`${node.name} is now ${next} in demo mode`);};
 const resetDemo=async()=>{const uploaded=state.files.filter(f=>f.origin==='local');await Promise.allSettled(uploaded.map(f=>deleteBlob(f.id)));setState(seedState);notify('Demo workspace restored to sample data');};
 const value=useMemo<VaultContextValue>(()=>({state,role,signIn,signOut,resetDemo,notify,toast,dismissToast:()=>setToast(null),uploadFiles,createFolder,renameFile,moveFile,toggleStar,trashFile,restoreFile,deleteFile,downloadFile,shareFile,revokeShare,toggleNode}),[state,role,toast,signIn,signOut,notify]);
 return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export function useVault(){const ctx=useContext(Ctx);if(!ctx)throw new Error('VaultProvider missing');return ctx;}
export {allowedEmail,MAX_BYTES};

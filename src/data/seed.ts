import type { VaultState } from '../types';
const t=(offset: number)=>new Date(Date.now()-offset*86400_000).toISOString();
export const seedState: VaultState = {
  folders: [
    {id:'folder-project',name:'Research & Projects',createdAt:t(24)},
    {id:'folder-academic',name:'Academic Records',createdAt:t(46)},
    {id:'folder-team',name:'Team Workspace',createdAt:t(8)}
  ],
  files: [
    {id:'seed-1',name:'Project Proposal.pdf',size:2498260,mime:'application/pdf',folderId:'folder-project',starred:true,status:'active',createdAt:t(2),updatedAt:t(2),owner:'Alex Morgan',origin:'sample',fragmentCount:5},
    {id:'seed-2',name:'Architecture Overview.fig',size:5321900,mime:'application/octet-stream',folderId:'folder-project',starred:false,status:'active',createdAt:t(3),updatedAt:t(3),owner:'Alex Morgan',origin:'sample',fragmentCount:5},
    {id:'seed-3',name:'Semester Report.docx',size:1834000,mime:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',folderId:'folder-academic',starred:false,status:'active',createdAt:t(6),updatedAt:t(6),owner:'Alex Morgan',origin:'sample',fragmentCount:5},
    {id:'seed-4',name:'Research Notes.md',size:47280,mime:'text/markdown',folderId:'folder-team',starred:true,status:'active',createdAt:t(8),updatedAt:t(8),owner:'Alex Morgan',origin:'sample',fragmentCount:5},
    {id:'seed-5',name:'System Requirements.xlsx',size:646800,mime:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',folderId:null,starred:false,status:'active',createdAt:t(9),updatedAt:t(9),owner:'Alex Morgan',origin:'sample',fragmentCount:5},
    {id:'seed-6',name:'Campus Photography.jpg',size:3824600,mime:'image/jpeg',folderId:null,starred:false,status:'active',createdAt:t(12),updatedAt:t(12),owner:'Alex Morgan',origin:'sample',fragmentCount:5},
  ],
  shares: [
    {id:'share-1',fileId:'seed-1',recipient:'priya@university.edu',permission:'view',createdAt:t(1),active:true},
    {id:'share-2',fileId:'seed-4',recipient:'rahul@university.edu',permission:'download',createdAt:t(5),active:true},
    {id:'share-3',fileId:'seed-3',recipient:'priya@university.edu',permission:'view',createdAt:t(7),active:false}
  ],
  activities: [
    {id:'act-1',type:'SHARE',title:'Access granted',detail:'Project Proposal.pdf shared with priya@university.edu',createdAt:t(.08),txId:'SIM-7BA4E1C9',actor:'Alex Morgan'},
    {id:'act-2',type:'UPLOAD',title:'Document uploaded',detail:'Project Proposal.pdf added to your vault',createdAt:t(.45),txId:'SIM-19C3A2F7',actor:'Alex Morgan'},
    {id:'act-3',type:'REVOKE',title:'Access revoked',detail:'Access to Semester Report.docx revoked',createdAt:t(1),txId:'SIM-6FA87A21',actor:'Alex Morgan'},
    {id:'act-4',type:'ADMIN',title:'Storage health checked',detail:'6 demo storage contributions evaluated',createdAt:t(2),txId:'SIM-3E1CB090',actor:'Platform operations'},
    {id:'act-5',type:'UPLOAD',title:'Document uploaded',detail:'Research Notes.md added to your vault',createdAt:t(5),txId:'SIM-F25A84D0',actor:'Alex Morgan'}
  ],
  nodes: [
    {id:'node-1',name:'Node Alpha',label:'Student contribution',provider:'Google Drive',used:164,capacity:250,status:'online'},
    {id:'node-2',name:'Node Beta',label:'Student contribution',provider:'Google Drive',used:187,capacity:250,status:'online'},
    {id:'node-3',name:'Node Gamma',label:'Student contribution',provider:'Google Drive',used:151,capacity:250,status:'online'},
    {id:'node-4',name:'Node Delta',label:'Student contribution',provider:'Google Drive',used:176,capacity:250,status:'online'},
    {id:'node-5',name:'Node Epsilon',label:'Student contribution',provider:'Google Drive',used:194,capacity:250,status:'online'},
    {id:'node-6',name:'Node Zeta',label:'Student contribution',provider:'Google Drive',used:171,capacity:250,status:'online'}
  ]
};

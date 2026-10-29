import {useState} from 'react';
import {motion} from 'framer-motion';
import {Check, LockKeyhole, ShieldCheck} from 'lucide-react';
const nodes=[{x:140,y:168},{x:278,y:78},{x:440,y:142},{x:463,y:313},{x:304,y:396},{x:131,y:332}];
export function NetworkVisual({compact=false}:{compact?:boolean}){
 const [active,setActive]=useState(2);
 return <div className={`network-visual relative ${compact?'network-compact':'network-full'}`} aria-label="Interactive illustration of a document connected to six distributed storage nodes">
  <div className="orb-halo orb-halo-1"/><div className="orb-halo orb-halo-2"/>
  <svg className="absolute inset-0 w-full h-full" viewBox="0 0 600 470" aria-hidden="true">
   <defs><linearGradient id="line-glow" x1="0" x2="1"><stop stopColor="#729bff" stopOpacity=".12"/><stop offset=".5" stopColor="#3e7ffc" stopOpacity=".65"/><stop offset="1" stopColor="#86dffd" stopOpacity=".2"/></linearGradient><radialGradient id="center-glow"><stop stopColor="#72b1ff" stopOpacity=".26"/><stop offset="1" stopColor="#72b1ff" stopOpacity="0"/></radialGradient></defs>
   <circle cx="301" cy="234" r="176" fill="url(#center-glow)"/>
   <ellipse cx="301" cy="234" rx="217" ry="140" stroke="#8facf5" strokeOpacity=".22" fill="none" strokeDasharray="5 7" transform="rotate(-29 301 234)"/>
   <ellipse cx="301" cy="234" rx="203" ry="166" stroke="#8facf5" strokeOpacity=".17" fill="none" transform="rotate(36 301 234)"/>
   {nodes.map((n,i)=><g key={i}><line x1="301" y1="234" x2={n.x} y2={n.y} stroke="url(#line-glow)" strokeWidth={i===active?2.3:1.25} strokeDasharray={i===active?'':'6 6'}/><circle cx={n.x} cy={n.y} r={i===active?29:23} fill={i===active?'#dceaff':'#f2f7ff'} stroke={i===active?'#528bff':'#c7d7f7'} strokeWidth="1.5"/><circle cx={n.x} cy={n.y} r="8" fill={i===active?'#2967fb':'#86a8ed'}/>{i===active&&<circle cx={n.x} cy={n.y} r="35" stroke="#689afa" strokeOpacity=".3" fill="none"/>}</g>)}
  </svg>
  <div className="center-document">
    <div className="doc-glyph"><LockKeyhole size={28} strokeWidth={1.7}/></div>
    <strong>Encrypted file</strong><span>Private by design</span>
  </div>
  {nodes.map((n,i)=><button key={i} className="absolute rounded-full focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300/70" style={{left:`${n.x/600*100}%`,top:`${n.y/470*100}%`,transform:'translate(-50%,-50%)',width:compact?38:52,height:compact?38:52}} onMouseEnter={()=>setActive(i)} onFocus={()=>setActive(i)} onClick={()=>setActive(i)} aria-label={`Inspect demo storage node ${i+1}`} title={`Node ${['Alpha','Beta','Gamma','Delta','Epsilon','Zeta'][i]}`} />)}
  {!compact&&<><motion.div className="float-chip chip-top" animate={{y:[0,-7,0]}} transition={{duration:5,repeat:Infinity}}><span className="chip-icon bg-blue-100 text-blue-600"><ShieldCheck size={17}/></span><span><strong>Access verified</strong><small>Policy check · simulated</small></span><Check size={15} className="text-emerald-500 ml-auto"/></motion.div>
  <motion.div className="float-chip chip-bottom" animate={{y:[0,8,0]}} transition={{duration:5.5,repeat:Infinity}}><span className="chip-icon bg-cyan-100 text-cyan-600"><span className="font-bold text-[10px]">05</span></span><span><strong>Distributed by design</strong><small>Fragment map · preview</small></span><span className="live-dot"/></motion.div></>}
 </div>
}

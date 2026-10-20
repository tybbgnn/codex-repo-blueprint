// Retain Node/Playwright scratch directories instead of deleting files.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=process.env.BLUEPRINT_SCRATCH_ROOT;
if(root){
 const archive=path.join(path.resolve(root),'.retained-node'),rename=fs.renameSync.bind(fs);
 function retain(name,opts={}){
  const p=path.resolve(String(name));
  if(!fs.existsSync(p)){if(opts.force)return;const e=new Error('Missing '+p);e.code='ENOENT';throw e;}
  if(!p.startsWith(path.resolve(root)+path.sep))throw new Error('Cleanup outside declared scratch: '+p);
  fs.mkdirSync(archive,{recursive:true});rename(p,path.join(archive,crypto.randomUUID()+'-'+path.basename(p)));
 }
 for(const key of ['rmSync','unlinkSync','rmdirSync'])fs[key]=(name,opts)=>retain(name,opts);
 for(const key of ['rm','unlink','rmdir']){
  fs[key]=(name,opts,callback)=>{if(typeof opts==='function'){callback=opts;opts={};}try{retain(name,opts);callback?.(null);}catch(e){callback?.(e);}};
  fs.promises[key]=async(name,opts)=>retain(name,opts);
 }
}

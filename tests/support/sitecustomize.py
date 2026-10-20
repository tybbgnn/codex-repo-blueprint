"""Preserve test scratch instead of deleting it; inherited by Python children."""
import os,shutil,uuid
from pathlib import Path
boundary=os.environ.get('BLUEPRINT_SCRATCH_ROOT')
if boundary:
 root=Path(boundary).resolve();archive=root/'.retained';rename=os.rename
 def retain(path,*,missing_ok=False,dir_fd=None):
  if dir_fd is not None:raise PermissionError('Descriptor-relative deletion is not permitted in retained tests')
  p=Path(path).absolute()
  if not p.exists() and not p.is_symlink():
   if missing_ok:return
   raise FileNotFoundError(str(p))
  if not p.is_relative_to(root) or p==root:raise PermissionError('Cleanup outside declared scratch is forbidden: '+str(p))
  archive.mkdir(parents=True,exist_ok=True);rename(p,archive/(uuid.uuid4().hex+'-'+p.name))
 def unlink(path,*,dir_fd=None):return retain(path,dir_fd=dir_fd)
 def rmdir(path,*,dir_fd=None):return retain(path,dir_fd=dir_fd)
 def rmtree(path,ignore_errors=False,onerror=None,*,onexc=None,dir_fd=None):
  try:return retain(path,missing_ok=ignore_errors,dir_fd=dir_fd)
  except Exception:
   if not ignore_errors:raise
 os.unlink=unlink;os.remove=unlink;os.rmdir=rmdir;shutil.rmtree=rmtree

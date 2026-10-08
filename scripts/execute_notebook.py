"""Execute all cells and save real outputs; default IPython avoids socket requirements.

Use --engine kernel for nbclient and a separate standard Jupyter kernel.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import json
import os
import sys
import nbformat

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--engine',choices=['ipython','kernel'],default='ipython')
args=parser.parse_args()
os.environ.setdefault('MPLCONFIGDIR',str(root/'.jupyter/matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME',str(root/'.jupyter/cache'))
os.environ.setdefault('JUPYTER_RUNTIME_DIR',str(root/'.jupyter/runtime'))
os.environ.setdefault('IPYTHONDIR',str(root/'.jupyter/ipython'))
for folder in ['matplotlib','cache','runtime','ipython']:
    (root/'.jupyter'/folder).mkdir(parents=True,exist_ok=True)
path=root/'f1_weather_2025.ipynb'
notebook=nbformat.read(path,as_version=4)
os.chdir(root)
if args.engine=='kernel':
    from nbclient import NotebookClient
    from jupyter_client import AsyncKernelManager
    data_dir=root/'.jupyter/data'
    kernel_dir=data_dir/'kernels/python3';kernel_dir.mkdir(parents=True,exist_ok=True)
    (kernel_dir/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
                                                    'display_name':'Python 3','language':'python'}))
    os.environ['JUPYTER_PATH']=str(data_dir)+os.pathsep+os.environ.get('JUPYTER_PATH','')
    kernel=AsyncKernelManager(kernel_name='python3',transport='tcp',ip='127.0.0.1')
    client=NotebookClient(notebook,timeout=300,km=kernel,resources={'metadata':{'path':str(root)}})
    client.execute()
else:
    from IPython.terminal.interactiveshell import TerminalInteractiveShell
    from IPython.utils.capture import capture_output
    shell=TerminalInteractiveShell.instance()
    shell.display_formatter.active_types=['text/plain','text/html','text/markdown','image/png','image/svg+xml','application/json']
    for cell in notebook.cells:
        if cell.cell_type!='code': continue
        cell.outputs=[]
        with capture_output(stdout=True,stderr=True,display=True) as captured:
            result=shell.run_cell(cell.source,store_history=True)
        result.raise_error()
        cell.execution_count=result.execution_count
        if captured.stdout:
            cell.outputs.append(nbformat.v4.new_output('stream',name='stdout',text=captured.stdout))
        if captured.stderr:
            cell.outputs.append(nbformat.v4.new_output('stream',name='stderr',text=captured.stderr))
        for output in captured.outputs:
            cell.outputs.append(nbformat.v4.new_output('display_data',data=output.data,metadata=output.metadata))
        print(f'Executed cell {cell.execution_count}',flush=True)
notebook.metadata['execution']={'engine':args.engine,'executed_at_utc':datetime.now(timezone.utc).isoformat(),
                                'offline':True,'note':'All code cells executed from source and outputs captured; no fabricated output.'}
nbformat.validate(notebook)
nbformat.write(notebook,path)
code_cells=[c for c in notebook.cells if c.cell_type=='code']
errors=[o for c in code_cells for o in c.get('outputs',[]) if o.output_type=='error']
assert all(c.execution_count is not None for c in code_cells)
assert not errors
images=sum('image/png' in o.get('data',{}) for c in code_cells for o in c.get('outputs',[]))
assert images >= 5, f'Expected 5 embedded charts, found {images}'
assert any('text/markdown' in o.get('data',{}) for c in code_cells for o in c.get('outputs',[])), 'Missing rendered results summary'
print(f'Executed {len(code_cells)} code cells with 0 errors and {images} chart outputs using {args.engine}: {path.name}')

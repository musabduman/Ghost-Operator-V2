import compileall, sys, pathlib
project_path = pathlib.Path(r'C:\Users\dum4n\Desktop\vs.code\asistan\FlightSim')
result = compileall.compile_dir(str(project_path), force=True, quiet=1)
if result:
    print('All files compiled successfully.')
else:
    sys.exit('Compilation errors detected.')

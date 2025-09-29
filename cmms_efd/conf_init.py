import os

rootf = "."

for currentp, dirs, files in os.walk(rootf):
    initf = os.path.join(currentp, "__init__.py")
    if "__init__.py" not in files:
        open(initf, "w").close()
        print("Creado: init_file")
    else:
        print("ya existe innit_file")

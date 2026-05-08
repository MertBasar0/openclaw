mods=['ifcopenshell','bonsai','blenderbim']
for m in mods:
    try:
        __import__(m)
        print(m + ': available')
    except Exception as e:
        print(m + ': missing ' + e.__class__.__name__)

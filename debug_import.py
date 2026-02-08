import sys
print('Python path:')
for p in sys.path:
    print(p)

print('\nTrying import...')
try:
    from backend.ethos_testing import api
    print('Import successful')
except Exception as e:
    print(f'Import failed: {e}')

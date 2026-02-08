from backend.ethos_testing.api import router

print('Router routes:')
for route in router.routes:
    print(f'  {route.methods} {route.path}')

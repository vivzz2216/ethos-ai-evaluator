try:
    from ethos_testing.api import router as ethos_router
    print('Direct import successful')
    print('Router prefix:', ethos_router.prefix)
except Exception as e:
    print('Direct import failed:', e)

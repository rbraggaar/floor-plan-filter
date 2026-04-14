def classFactory(iface):  # noqa: N802
    from .floor_navigator import FloorNavigator
    return FloorNavigator(iface)

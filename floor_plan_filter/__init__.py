# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FloorPlanFilter
                                 A QGIS plugin
 This plugin applies a query filter to multiple map layers to visualize individual floor plans.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2021-02-19
        copyright            : (C) 2021 by Rob Braggaar
        email                : rcbraggaar@gmail.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load FloorPlanFilter class from file FloorPlanFilter.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .floor_plan_filter import FloorPlanFilter
    return FloorPlanFilter(iface)

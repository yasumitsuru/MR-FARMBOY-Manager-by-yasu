import QtQuick
import ".." as AppTheme

Rectangle {
    default property alias content: contentArea.data
    property bool raised: false
    color: raised ? AppTheme.Theme.surfaceRaised : AppTheme.Theme.surface
    radius: AppTheme.Theme.radiusCard
    border.width: AppTheme.Theme.borderWidth
    border.color: AppTheme.Theme.border
    implicitWidth: 240
    implicitHeight: 120

    Behavior on color { ColorAnimation { duration: AppTheme.Theme.motionFast } }

    Item { id: contentArea; anchors.fill: parent; anchors.margins: AppTheme.Theme.space16 }
}

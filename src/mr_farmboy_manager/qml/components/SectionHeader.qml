import QtQuick
import QtQuick.Layouts
import ".." as AppTheme

Item {
    id: header
    property string title: ""
    property string subtitle: ""
    default property alias action: actionSlot.data
    implicitHeight: Math.max(textColumn.implicitHeight, actionSlot.implicitHeight)
    RowLayout {
        anchors.fill: parent
        spacing: AppTheme.Theme.space16
        ColumnLayout {
            id: textColumn
            Layout.fillWidth: true
            spacing: AppTheme.Theme.space4
            Text { id: titleLabel; objectName: header.objectName.length > 0 ? header.objectName + "Title" : ""; Layout.fillWidth: true; text: title; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.displayFont; font.pixelSize: AppTheme.Theme.typePageTitle; font.weight: AppTheme.Theme.weightBold; elide: Text.ElideRight }
            Text { Layout.fillWidth: true; visible: subtitle.length > 0; text: subtitle; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; elide: Text.ElideRight }
        }
        Item { id: actionSlot; objectName: header.objectName.length > 0 ? header.objectName + "Action" : ""; implicitWidth: childrenRect.width; implicitHeight: childrenRect.height; Layout.alignment: Qt.AlignRight | Qt.AlignVCenter }
    }
}

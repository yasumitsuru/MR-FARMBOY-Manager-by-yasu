import QtQuick
import QtQuick.Layouts
import ".." as AppTheme

Item {
    property string title: ""
    property string subtitle: ""
    property alias action: actionSlot.data
    implicitHeight: Math.max(textColumn.implicitHeight, actionSlot.implicitHeight)
    RowLayout {
        anchors.fill: parent
        spacing: AppTheme.Theme.space16
        ColumnLayout {
            id: textColumn
            Layout.fillWidth: true
            spacing: AppTheme.Theme.space4
            Text { text: title; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.displayFont; font.pixelSize: AppTheme.Theme.typePageTitle; font.weight: AppTheme.Theme.weightBold }
            Text { visible: subtitle.length > 0; text: subtitle; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody }
        }
        Item { id: actionSlot; Layout.alignment: Qt.AlignRight | Qt.AlignVCenter }
    }
}

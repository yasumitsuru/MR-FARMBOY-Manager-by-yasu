import QtQuick
import QtQuick.Layouts
import ".." as AppTheme

Item {
    property string label: ""
    property string value: ""
    implicitHeight: AppTheme.Theme.controlHeight
    RowLayout {
        anchors.fill: parent
        spacing: AppTheme.Theme.space12
        Text { text: label; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; Layout.fillWidth: true; elide: Text.ElideRight }
        Text { text: value; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta; horizontalAlignment: Text.AlignRight; elide: Text.ElideLeft }
    }
}

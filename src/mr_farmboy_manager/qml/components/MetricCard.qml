import QtQuick
import QtQuick.Layouts
import ".." as AppTheme

AppCard {
    property string label: ""
    property string value: "—"
    property string detail: ""
    implicitHeight: 136
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: AppTheme.Theme.space16
        spacing: AppTheme.Theme.space8
        Text { text: label; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeMeta; font.weight: AppTheme.Theme.weightSemibold }
        Text { text: value; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.displayFont; font.pixelSize: AppTheme.Theme.typeMetric; font.weight: AppTheme.Theme.weightBold; Layout.fillWidth: true; elide: Text.ElideRight }
        Text { text: detail; color: AppTheme.Theme.textMuted; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta; Layout.fillWidth: true; elide: Text.ElideRight }
    }
}

import QtQuick
import ".." as AppTheme

Rectangle {
    property string status: "neutral"
    property string label: ""
    implicitWidth: badgeText.implicitWidth + AppTheme.Theme.space16
    implicitHeight: AppTheme.Theme.controlHeight
    radius: AppTheme.Theme.radiusControl
    color: AppTheme.Theme.surfaceMuted
    border.width: AppTheme.Theme.borderWidth
    border.color: status === "error" ? AppTheme.Theme.error : (status === "warning" ? AppTheme.Theme.warning : (status === "success" ? AppTheme.Theme.success : AppTheme.Theme.border))
    Accessible.name: label
    Text { id: badgeText; anchors.centerIn: parent; text: label; color: parent.border.color; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeMeta; font.weight: AppTheme.Theme.weightSemibold }
}

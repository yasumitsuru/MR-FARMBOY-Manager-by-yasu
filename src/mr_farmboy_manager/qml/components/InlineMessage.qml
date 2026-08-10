import QtQuick
import ".." as AppTheme

Rectangle {
    property string severity: "info"
    property string message: ""
    implicitHeight: messageText.implicitHeight + AppTheme.Theme.space16
    color: AppTheme.Theme.surfaceMuted
    radius: AppTheme.Theme.radiusControl
    border.width: AppTheme.Theme.borderWidth
    border.color: severity === "error" ? AppTheme.Theme.error : (severity === "warning" ? AppTheme.Theme.warning : AppTheme.Theme.border)
    Text { id: messageText; anchors.fill: parent; anchors.margins: AppTheme.Theme.space8; text: parent.message; color: parent.severity === "error" ? AppTheme.Theme.error : AppTheme.Theme.textSecondary; wrapMode: Text.WordWrap; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody }
}

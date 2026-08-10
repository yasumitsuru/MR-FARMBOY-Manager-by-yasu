import QtQuick
import QtQuick.Controls
import ".." as AppTheme

Button {
    property string variant: "secondary"
    property string tooltipText: ""
    implicitHeight: variant === "primary" ? AppTheme.Theme.primaryActionHeight : AppTheme.Theme.controlHeight
    implicitWidth: Math.max(AppTheme.Theme.controlHeight, contentItem.implicitWidth + AppTheme.Theme.space24)
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    ToolTip.visible: hovered && tooltipText.length > 0
    ToolTip.text: tooltipText

    background: Rectangle {
        radius: AppTheme.Theme.radiusControl
        border.width: AppTheme.Theme.borderWidth
        border.color: parent.activeFocus ? AppTheme.Theme.focus : (parent.variant === "primary" ? AppTheme.Theme.accent : (parent.variant === "danger" ? AppTheme.Theme.error : AppTheme.Theme.border))
        color: parent.variant === "primary" ? (parent.down ? AppTheme.Theme.accentStrong : AppTheme.Theme.accent) : (parent.hovered ? AppTheme.Theme.surfaceRaised : AppTheme.Theme.surface)
        opacity: parent.enabled ? 1 : 0.55
        Behavior on color { ColorAnimation { duration: AppTheme.Theme.motionFast } }
    }
    contentItem: Text {
        text: parent.text
        color: parent.variant === "primary" ? AppTheme.Theme.background : (parent.variant === "danger" ? AppTheme.Theme.error : AppTheme.Theme.textPrimary)
        font.family: AppTheme.Theme.bodyFont
        font.weight: AppTheme.Theme.weightSemibold
        font.pixelSize: AppTheme.Theme.typeBody
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}

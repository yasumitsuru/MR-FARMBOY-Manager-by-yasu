import QtQuick
import QtQuick.Controls
import ".." as AppTheme

Button {
    id: item
    property string label: ""
    property string symbol: "•"
    property bool selected: false
    property bool compact: false
    signal activated()
    implicitHeight: AppTheme.Theme.primaryActionHeight
    implicitWidth: compact ? 64 : 200
    activeFocusOnTab: true
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: label

    background: Rectangle {
        radius: AppTheme.Theme.radiusControl
        color: item.selected ? AppTheme.Theme.surfaceRaised : AppTheme.Theme.transparent
        border.width: item.selected || item.activeFocus ? AppTheme.Theme.borderWidth : 0
        border.color: item.activeFocus ? AppTheme.Theme.focus : (item.selected ? AppTheme.Theme.accent : AppTheme.Theme.transparent)
        Behavior on color { ColorAnimation { duration: AppTheme.Theme.motionStandard } }
    }
    contentItem: Item {
        Rectangle { anchors.verticalCenter: parent.verticalCenter; x: AppTheme.Theme.space8; width: AppTheme.Theme.space4; height: item.selected ? 20 : AppTheme.Theme.space8; radius: width; color: item.selected ? AppTheme.Theme.accent : AppTheme.Theme.border; Behavior on height { NumberAnimation { duration: AppTheme.Theme.motionStandard } } }
        Text { anchors.verticalCenter: parent.verticalCenter; x: AppTheme.Theme.space20; text: item.symbol; color: item.selected ? AppTheme.Theme.accent : AppTheme.Theme.textSecondary; font.pixelSize: AppTheme.Theme.typeCardTitle; font.family: AppTheme.Theme.bodyFont }
        Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 48; anchors.right: parent.right; anchors.rightMargin: AppTheme.Theme.space8; visible: !item.compact; text: item.label; color: item.selected ? AppTheme.Theme.textPrimary : AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; elide: Text.ElideRight }
    }
    onClicked: item.activated()
    Keys.onReturnPressed: item.activated()
    Keys.onEnterPressed: item.activated()
    ToolTip.visible: compact && hovered
    ToolTip.text: label
}

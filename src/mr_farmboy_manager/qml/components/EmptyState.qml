import QtQuick
import QtQuick.Layouts
import ".." as AppTheme

AppCard {
    property string title: "Nenhum dado disponível"
    property string message: "Escolha uma ação para continuar."
    property alias action: actionSlot.data
    implicitHeight: 176
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: AppTheme.Theme.space24
        spacing: AppTheme.Theme.space8
        Text { text: title; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.displayFont; font.pixelSize: AppTheme.Theme.typeCardTitle; font.weight: AppTheme.Theme.weightBold }
        Text { text: message; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Item { id: actionSlot; Layout.fillWidth: true; Layout.fillHeight: true }
    }
}

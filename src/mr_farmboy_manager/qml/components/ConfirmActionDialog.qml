import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as AppTheme

Dialog {
    id: dialog
    property string action: ""
    property string backupId: ""
    property string confirmationTitle: "Confirmar ação"
    property string confirmationMessage: ""
    signal confirmed(string action, string backupId)
    signal cancelled()
    modal: true
    focus: true
    title: confirmationTitle
    width: 420
    standardButtons: Dialog.NoButton
    function openConfirmation(actionValue, backupIdValue, titleValue, messageValue) {
        action = actionValue
        backupId = backupIdValue
        confirmationTitle = titleValue
        confirmationMessage = messageValue
        open()
    }
    background: Rectangle { color: AppTheme.Theme.surface; radius: AppTheme.Theme.radiusPanel; border.width: AppTheme.Theme.borderWidth; border.color: AppTheme.Theme.border }
    contentItem: ColumnLayout {
        spacing: AppTheme.Theme.space16
        Text { text: dialog.confirmationMessage; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; wrapMode: Text.WordWrap; Layout.preferredWidth: 360 }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            AppButton { objectName: "confirmDialogCancelButton"; text: "Cancelar"; onClicked: { dialog.cancelled(); dialog.close() } }
            AppButton { objectName: "confirmDialogConfirmButton"; text: "Confirmar"; variant: dialog.action === "delete" ? "danger" : "primary"; onClicked: { dialog.confirmed(dialog.action, dialog.backupId); dialog.close() } }
        }
    }
}

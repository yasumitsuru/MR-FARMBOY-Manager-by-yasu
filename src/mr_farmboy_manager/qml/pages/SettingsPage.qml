import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".." as AppTheme

Item {
    id: page
    objectName: "settingsPage"
    property var controller
    property var settings: controller ? controller.settings : null
    property var shell
    readonly property bool narrowLayout: width < 700

    function badgeLabel(state) {
        if (state === "valid") return "Válido"
        if (state === "empty") return "Não definido"
        return "Inválido"
    }

    function badgeStatus(state) {
        if (state === "valid") return "success"
        if (state === "empty") return "neutral"
        return "error"
    }

    ScrollView {
        id: settingsScroll
        objectName: "settingsScrollView"
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: settingsScroll.availableWidth - AppTheme.Theme.space24 * 2
            x: AppTheme.Theme.space24
            spacing: AppTheme.Theme.space20

            AppCard {
                Layout.fillWidth: true
                implicitHeight: saveRootContent.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: saveRootContent
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space12
                    SectionHeader { Layout.fillWidth: true; title: "Raiz dos saves"; subtitle: "Pasta que contém os slots do jogo" }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Status"; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; Layout.fillWidth: true }
                        StatusBadge { objectName: "saveRootBadge"; status: page.badgeStatus(settings ? settings.saveRootState : "empty"); label: page.badgeLabel(settings ? settings.saveRootState : "empty") }
                    }
                    TextField {
                        objectName: "saveRootField"
                        Layout.fillWidth: true
                        text: settings ? settings.saveRoot : ""
                        placeholderText: "Selecione a pasta dos saves"
                        selectByMouse: true
                        onEditingFinished: if (settings) settings.setSaveRoot(text)
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        AppButton { objectName: "chooseSaveRootButton"; text: "Escolher pasta"; onClicked: if (settings) settings.chooseSaveRoot() }
                        Text { objectName: "saveRootMessage"; Layout.fillWidth: true; text: settings ? settings.saveRootMessage : ""; color: settings && page.badgeStatus(settings.saveRootState) === "error" ? AppTheme.Theme.error : AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; wrapMode: Text.WordWrap }
                    }
                }
            }

            AppCard {
                Layout.fillWidth: true
                implicitHeight: gameInstallContent.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: gameInstallContent
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space12
                    SectionHeader { Layout.fillWidth: true; title: "Instalação do jogo"; subtitle: "Usada para localizar arquivos e abrir o jogo" }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Status"; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; Layout.fillWidth: true }
                        StatusBadge { objectName: "gameInstallBadge"; status: page.badgeStatus(settings ? settings.gameInstallState : "empty"); label: page.badgeLabel(settings ? settings.gameInstallState : "empty") }
                    }
                    TextField { objectName: "gameInstallField"; Layout.fillWidth: true; text: settings ? settings.gameInstallRoot : ""; placeholderText: "Selecione a instalação do jogo"; selectByMouse: true; onEditingFinished: if (settings) settings.setGameInstallRoot(text) }
                    RowLayout {
                        Layout.fillWidth: true
                        AppButton { objectName: "chooseGameInstallButton"; text: "Escolher pasta"; onClicked: if (settings) settings.chooseGameInstallRoot() }
                        Text { Layout.fillWidth: true; text: settings ? settings.gameInstallMessage : ""; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; wrapMode: Text.WordWrap }
                    }
                }
            }

            AppCard {
                Layout.fillWidth: true
                implicitHeight: backupRootContent.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: backupRootContent
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space12
                    SectionHeader { Layout.fillWidth: true; title: "Backups"; subtitle: "Local protegido dos backups criados pelo gerenciador" }
                    TextEdit { Layout.fillWidth: true; readOnly: true; text: settings ? settings.backupRootLabel : "Não disponível"; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.utilityFont; wrapMode: TextEdit.WrapAnywhere; selectByMouse: true }
                    AppButton { objectName: "saveSettingsButton"; text: "Salvar configurações"; variant: "primary"; enabled: settings && settings.hasUnsavedChanges && settings.canSave; onClicked: if (settings) settings.save() }
                }
            }
        }
    }
}

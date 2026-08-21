import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".." as AppTheme

Item {
    id: page
    objectName: "savesPage"
    property var controller
    property var saves: controller ? controller.saves : null
    property var shell
    readonly property bool wideLayout: width >= 1100

    ScrollView {
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth
        GridLayout {
            width: parent.width - AppTheme.Theme.space24 * 2
            x: AppTheme.Theme.space24
            columns: page.wideLayout ? 2 : 1
            columnSpacing: AppTheme.Theme.space20
            rowSpacing: AppTheme.Theme.space20

            AppCard {
                id: ledgerPanel
                Layout.fillWidth: true
                Layout.preferredWidth: page.wideLayout ? parent.width * 0.34 : parent.width
                Layout.alignment: Qt.AlignTop
                implicitHeight: ledgerColumn.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: ledgerColumn
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space12
                    SectionHeader {
                        objectName: "savesLedgerHeader"
                        Layout.fillWidth: true
                        title: "Ledger de saves"
                        subtitle: "Selecione um slot para consultar sua evidência"
                        AppButton { objectName: "refreshSavesButton"; text: "Atualizar"; tooltipText: "Atualizar saves"; enabled: saves && saves.canRefresh; onClicked: saves.refresh() }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: AppTheme.Theme.borderWidth; color: AppTheme.Theme.border }
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: saves && saves.state === "ready" ? Math.max(AppTheme.Theme.primaryActionHeight, saveSlotsList.contentHeight) : AppTheme.Theme.primaryActionHeight * 3
                        ListView {
                            id: saveSlotsList
                            objectName: "saveSlotsList"
                            anchors.fill: parent
                            clip: true
                            visible: saves && saves.state === "ready"
                            model: saves ? saves.slotsModel : null
                            spacing: AppTheme.Theme.space8
                            delegate: Button {
                                id: saveDelegate
                                objectName: "saveRecord-" + slotId
                                required property string slotId
                                required property string displayName
                                required property int slotNumber
                                required property int recordCount
                                required property bool selected
                                width: saveSlotsList.width
                                implicitHeight: AppTheme.Theme.primaryActionHeight + AppTheme.Theme.space12
                                text: displayName + " · " + String(recordCount) + " registros"
                                focusPolicy: Qt.StrongFocus
                                Accessible.name: displayName + ", " + String(recordCount) + " registros"
                                onClicked: saves.selectSlot(slotId)
                                background: Rectangle {
                                    radius: AppTheme.Theme.radiusControl
                                    color: saveDelegate.hovered || saveDelegate.selected ? AppTheme.Theme.surfaceRaised : AppTheme.Theme.surface
                                    border.width: AppTheme.Theme.borderWidth
                                    border.color: saveDelegate.activeFocus ? AppTheme.Theme.focus : (saveDelegate.selected ? AppTheme.Theme.accent : AppTheme.Theme.border)
                                    Rectangle { anchors.left: parent.left; anchors.leftMargin: AppTheme.Theme.space8; anchors.verticalCenter: parent.verticalCenter; width: AppTheme.Theme.space4; height: saveDelegate.selected ? AppTheme.Theme.space20 : AppTheme.Theme.space8; radius: width; color: saveDelegate.selected ? AppTheme.Theme.accent : AppTheme.Theme.border }
                                }
                                contentItem: Text { text: saveDelegate.text; leftPadding: AppTheme.Theme.space24; rightPadding: AppTheme.Theme.space12; verticalAlignment: Text.AlignVCenter; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; elide: Text.ElideRight }
                            }
                        }
                        ColumnLayout {
                            anchors.fill: parent
                            visible: !saves || saves.state !== "ready"
                            spacing: AppTheme.Theme.space8
                            Text { text: saves && saves.state === "loading" ? "Lendo os slots…" : (saves && saves.state === "error" ? "Não foi possível carregar os saves." : "Nenhum save encontrado."); color: saves && saves.state === "error" ? AppTheme.Theme.error : AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            AppButton { visible: saves && saves.state === "error"; text: "Tentar novamente"; onClicked: saves.refresh() }
                        }
                    }
                }
            }

            AppCard {
                id: detailPanel
                objectName: "saveDetailsPanel"
                Layout.fillWidth: true
                Layout.preferredWidth: page.wideLayout ? parent.width * 0.66 : parent.width
                Layout.alignment: Qt.AlignTop
                implicitHeight: detailColumn.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: detailColumn
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space16
                    SectionHeader { Layout.fillWidth: true; title: "Evidência do save"; subtitle: saves && saves.selectedSlotId.length > 0 ? saves.selectedSlotId : "Nenhum slot selecionado" }
                    InlineMessage { objectName: "savesErrorMessage"; Layout.fillWidth: true; visible: saves && (saves.state === "error" || saves.detailsState === "error"); severity: "error"; message: saves ? saves.errorMessage : "" }
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: detailBody.implicitHeight
                        ColumnLayout {
                            id: detailBody
                            anchors.fill: parent
                            spacing: AppTheme.Theme.space16
                            visible: saves && saves.state === "ready" && saves.selectedSlotId.length > 0 && saves.detailsState === "ready"
                            GridLayout {
                                Layout.fillWidth: true; columns: width >= 700 ? 3 : 1
                                columnSpacing: AppTheme.Theme.space16; rowSpacing: AppTheme.Theme.space4
                                InfoRow {
                                    Layout.fillWidth: true; label: "Registros"; value: saves ? String(saves.details.recordCount) : "—"
                                    Text { objectName: "saveDetailRecordCount"; visible: false; text: saves ? String(saves.details.recordCount) : "—" }
                                }
                                InfoRow { Layout.fillWidth: true; label: "Plantados"; value: saves ? String(saves.details.plantedCount) : "—" }
                                InfoRow { Layout.fillWidth: true; label: "Regados"; value: saves ? String(saves.details.wateredCount) : "—" }
                            }
                            GridLayout {
                                Layout.fillWidth: true; columns: width >= 700 ? 4 : 1
                                columnSpacing: AppTheme.Theme.space16; rowSpacing: AppTheme.Theme.space4
                                InfoRow { Layout.fillWidth: true; label: "Fertilizados"; value: saves ? String(saves.details.fertilizedCount) : "—" }
                                InfoRow { Layout.fillWidth: true; label: "Maduros"; value: saves ? String(saves.details.maturedCount) : "—" }
                                InfoRow { Layout.fillWidth: true; label: "Colhíveis"; value: saves ? String(saves.details.harvestableCount) : "—" }
                                InfoRow { Layout.fillWidth: true; label: "Mortos"; value: saves ? String(saves.details.deadCount) : "—" }
                            }
                            Repeater {
                                model: saves && saves.details ? saves.details.growthStatesModel : null
                                delegate: ColumnLayout {
                                    required property string label; required property int value; required property real ratio
                                    Layout.fillWidth: true; spacing: AppTheme.Theme.space4
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text { text: label; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; Layout.fillWidth: true }
                                        Text { text: String(value); color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.utilityFont }
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true; Layout.preferredHeight: AppTheme.Theme.space4; color: AppTheme.Theme.surfaceMuted; radius: height
                                        Rectangle { width: parent.width * Math.max(0, Math.min(1, ratio)); height: parent.height; radius: height; color: AppTheme.Theme.accent }
                                    }
                                }
                            }
                            GridLayout {
                                Layout.fillWidth: true; columns: width >= 700 ? 3 : 1; columnSpacing: AppTheme.Theme.space16
                                InfoRow { Layout.fillWidth: true; label: "Arquivos lidos"; value: saves ? String(saves.details.inspectedFileCount) : "—" }
                                InfoRow { Layout.fillWidth: true; label: "Falhas"; value: saves ? String(saves.details.failedFileCount) : "—" }
                                InfoRow { Layout.fillWidth: true; label: "Última modificação"; value: saves ? saves.details.latestModifiedLabel : "Não disponível" }
                            }
                            AppButton { text: "Criar backup deste save"; variant: "primary"; enabled: saves && saves.canCreateBackup; onClicked: controller.backups.createForSelectedSlot() }
                        }
                        Text { anchors.fill: parent; visible: !detailBody.visible; text: saves && saves.detailsState === "loading" ? "Carregando a evidência do slot…" : "Selecione um save para ver o resumo, a produção e o crescimento."; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; wrapMode: Text.WordWrap }
                    }
                }
            }
        }
    }
}

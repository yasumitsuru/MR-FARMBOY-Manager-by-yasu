import QtQuick
import QtQuick.Controls
import "components"
import "." as AppTheme

ApplicationWindow {
    objectName: "mainWindow"
    width: 1366
    height: 768
    minimumWidth: 960
    minimumHeight: 640
    visible: true
    color: AppTheme.Theme.background
    title: "MR FARMBOY Manager"

    AppShell {
        objectName: "appShell"
        anchors.fill: parent
        controller: appController
    }
}

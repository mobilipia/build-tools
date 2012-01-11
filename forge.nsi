;NSIS Modern User Interface
;Header Bitmap Example Script
;Written by Joost Verburg

;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"

;--------------------------------
;General

  ;Name and file
  Name "Forge Tools"
  OutFile "Install Forge.exe"

  ;Default installation folder
  InstallDir "$LOCALAPPDATA\Forge Tools"
  
  ;Get installation folder from registry if available
  InstallDirRegKey HKCU "Software\Modern UI Test" ""

  ;Request application privileges for Windows Vista
  RequestExecutionLevel user

;--------------------------------
;Interface Configuration

  !define MUI_HEADERIMAGE
  !define MUI_HEADERIMAGE_BITMAP "${NSISDIR}\Contrib\Graphics\Header\nsis.bmp" ; optional
  !define MUI_ABORTWARNING
  
  ;!define MUI_WELCOMEPAGE_TITLE "Hello World"
  !define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through installing the Forge build tools.$\r$\n$\r$\nAfterwards you will be able to start making apps using Forge!"
  
  !define MUI_FINISHPAGE_RUN $INSTDIR\forge.exe
  !define MUI_FINISHPAGE_RUN_TEXT "Run the Forge build tools now"
  !define MUI_FINISHPAGE_RUN_PARAMETERS web
  
;--------------------------------
;Pages

  !insertmacro MUI_PAGE_WELCOME
  !insertmacro MUI_PAGE_LICENSE "nsis\license.txt"
  ;!insertmacro MUI_PAGE_COMPONENTS
  ;!insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES
  !insertmacro MUI_PAGE_FINISH
  
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  
;--------------------------------
;Languages
 
  !insertmacro MUI_LANGUAGE "English"

;--------------------------------
;Installer Sections

Section "Dummy Section" SecDummy

  SetOutPath "$INSTDIR"
  
  ;ADD YOUR OWN FILES HERE...
  File forge_build.json
  File forge.exe
  File debug.keystore
  
  ;Start menu entries
  CreateDirectory "$SMPROGRAMS\Forge"
  CreateShortCut "$SMPROGRAMS\Forge\Forge Tools.lnk" "$INSTDIR\forge.exe" "web"
  CreateShortCut "$SMPROGRAMS\Forge\Uninstall Forge Tools.lnk" "$INSTDIR\Uninstall.exe"
  
  ;Store installation folder
  WriteRegStr HKCU "Software\Forge Tools" "" $INSTDIR
  
  ;Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

SectionEnd

;--------------------------------
;Descriptions

  ;Language strings
  LangString DESC_SecDummy ${LANG_ENGLISH} "A test section."

  ;Assign language strings to sections
  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDummy} $(DESC_SecDummy)
  !insertmacro MUI_FUNCTION_DESCRIPTION_END
 
;--------------------------------
;Uninstaller Section

Section "Uninstall"

  ;ADD YOUR OWN FILES HERE...

  Delete "$INSTDIR\Uninstall.exe"
  
  Delete "$INSTDIR\forge_build.json"
  Delete "$INSTDIR\forge.exe"
  Delete "$INSTDIR\debug.keystore"
  
  Delete "$SMPROGRAMS\Forge\Forge Tools.lnk"
  Delete "$SMPROGRAMS\Forge\Uninstall Forge Tools.lnk"
  Delete "$SMPROGRAMS\Forge"

  RMDir "$INSTDIR"

  DeleteRegKey /ifempty HKCU "Software\Forge Tools"

SectionEnd
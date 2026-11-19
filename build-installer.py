from pathlib import Path
import uuid,xml.etree.ElementTree as E
base=Path(__file__).resolve().parent;payload=base/'dist'/'VesperService';out=base/'build'/'installer';out.mkdir(parents=True,exist_ok=True)
ns='http://schemas.microsoft.com/wix/2006/wi';util='http://schemas.microsoft.com/wix/UtilExtension';E.register_namespace('',ns);E.register_namespace('util',util)
def el(parent,tag,**attrs):return E.SubElement(parent,'{'+ns+'}'+tag,{k:str(v) for k,v in attrs.items()})
w=E.Element('{'+ns+'}Wix');product=el(w,'Product',Id='*',Name='Vesper Keep Player',Language='1033',Version='0.1.2',Manufacturer='Vesper Keep',UpgradeCode='936456D7-761A-4BEF-B729-EE92BDAAFA53')
el(product,'Package',InstallerVersion='500',Compressed='yes',InstallScope='perUser',Platform='x64',Description='Vesper Keep Player preview')
el(product,'MajorUpgrade',DowngradeErrorMessage='A newer Vesper Keep Player is already installed.')
el(product,'MediaTemplate',EmbedCab='yes')
el(product,'Icon',Id='VesperIconV2',SourceFile=str(payload/'vesper.ico'));el(product,'Property',Id='ARPPRODUCTICON',Value='VesperIconV2');el(product,'Property',Id='ARPHELPLINK',Value='https://vesperkeep.duckdns.org/')

root=el(product,'Directory',Id='TARGETDIR',Name='SourceDir');local=el(root,'Directory',Id='LocalAppDataFolder');install=el(local,'Directory',Id='INSTALLFOLDER',Name='Vesper Keep Player')
programs=el(root,'Directory',Id='ProgramMenuFolder');menu=el(programs,'Directory',Id='VesperMenu',Name='Vesper Keep Player');el(root,'Directory',Id='DesktopFolder')
feature=el(product,'Feature',Id='Main',Title='Vesper Keep Player',Level='1')
fileids={}
def ident(prefix,value):return prefix+uuid.uuid5(uuid.NAMESPACE_URL,value).hex
for folder in [payload]+sorted(x for x in payload.rglob('*') if x.is_dir()):
 rel=folder.relative_to(payload);parent=install
 for part_index in range(len(rel.parts)):
  partial=Path(*rel.parts[:part_index+1]).as_posix();did=ident('D',partial)
  found=next((x for x in parent if x.tag.endswith('Directory') and x.get('Id')==did),None)
  parent=found if found is not None else el(parent,'Directory',Id=did,Name=rel.parts[part_index])
 for f in sorted(folder.iterdir()):
  if not f.is_file():continue
  relative=f.relative_to(payload).as_posix();cid=ident('C',relative);fid=ident('F',relative);fileids[relative]=fid
  comp=el(parent,'Component',Id=cid,Guid=str(uuid.uuid5(uuid.NAMESPACE_URL,'vesperkeep/0.1/'+relative)).upper(),Win64='yes')
  el(comp,'File',Id=fid,Source=str(f),**({'DefaultLanguage':'1033'} if f.suffix.lower()=='.ttf' else {}));el(comp,'RegistryValue',Root='HKCU',Key=r'Software\VesperKeep\Player\Files',Name=cid,Type='integer',Value='1',KeyPath='yes');el(comp,'RemoveFolder',Id=ident('R',relative),On='uninstall');el(feature,'ComponentRef',Id=cid)
comp=el(install,'Component',Id='VesperShortcuts',Guid='86133D39-5455-4C4C-894A-C87F07FB8BC3',Win64='yes')
for directory,sid in [('DesktopFolder','DesktopLink'),('VesperMenu','MenuLink')]:el(comp,'Shortcut',Id=sid,Directory=directory,Name='Vesper Keep Player',Target='[INSTALLFOLDER]Vesper Keep Player.exe',WorkingDirectory='INSTALLFOLDER',Icon='VesperIconV2',Advertise='no')
el(comp,'Shortcut',Id='GuideLink',Directory='VesperMenu',Name='How to use Vesper',Target='[INSTALLFOLDER]Start here.html',WorkingDirectory='INSTALLFOLDER',Advertise='no')
el(comp,'RegistryValue',Root='HKCU',Key=r'Software\VesperKeep\Player',Name='InstallDir',Type='string',Value='[INSTALLFOLDER]',KeyPath='yes')
el(comp,'RegistryValue',Root='HKCU',Key=r'Software\VesperKeep\Player',Name='DataDir',Type='string',Value='[INSTALLFOLDER]Data')
el(comp,'RemoveFolder',Id='RemoveVesperMenu',Directory='VesperMenu',On='uninstall');el(feature,'ComponentRef',Id='VesperShortcuts')
for directory in install.iter('{'+ns+'}Directory'):el(comp,'RemoveFolder',Id=ident('RD',directory.get('Id')),Directory=directory.get('Id'),On='uninstall')
prop=el(product,'Property',Id='VESPERDATA');el(prop,'RegistrySearch',Id='FindVesperData',Root='HKCU',Key=r'Software\VesperKeep\Player',Name='DataDir',Type='raw',Win64='yes')
cleanup=el(install,'Component',Id='RuntimeCleanup',Guid='FC5368E0-323F-4F31-87D2-5CAC7E545039',Win64='yes');el(cleanup,'RegistryValue',Root='HKCU',Key=r'Software\VesperKeep\Player',Name='RuntimeOwned',Type='integer',Value='1',KeyPath='yes');E.SubElement(cleanup,'{'+util+'}RemoveFolderEx',{'Id':'RemoveVesperRuntime','On':'uninstall','Property':'VESPERDATA'});el(feature,'ComponentRef',Id='RuntimeCleanup')
saved=el(product,'Property',Id='INSTALLFOLDER');el(saved,'RegistrySearch',Id='FindVesperInstall',Root='HKCU',Key=r'Software\VesperKeep\Player',Name='InstallDir',Type='raw',Win64='yes')
el(product,'Property',Id='WIXUI_INSTALLDIR',Value='INSTALLFOLDER');el(product,'UIRef',Id='WixUI_InstallDir')
ui=el(product,'UI');el(ui,'Publish',Dialog='WelcomeDlg',Control='Next',Event='NewDialog',Value='InstallDirDlg',Order='2').text='NOT Installed';el(ui,'Publish',Dialog='InstallDirDlg',Control='Back',Event='NewDialog',Value='WelcomeDlg',Order='2').text='1'
E.indent(w);E.ElementTree(w).write(out/'Player.wxs',encoding='utf-8',xml_declaration=True)
print('Installer source generated;',len(fileids),'explicit application files; no libraries/accounts/media included.')
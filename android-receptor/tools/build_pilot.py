"""Compila con un SDK oficial ya instalado; no descarga herramientas ni usa credenciales del negocio."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--android-jar',type=Path,required=True)
    parser.add_argument('--build-tools',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];build=root/'build/local'
    classes=build/'classes';dex=build/'dex';classes.mkdir(parents=True,exist_ok=True);dex.mkdir(exist_ok=True)
    for folder in [classes,dex]:
        for path in folder.iterdir():
            if path.is_dir():shutil.rmtree(path)
            else:path.unlink()
    sdk=args.android_jar.resolve();tools=args.build_tools.resolve()
    def run(*parts):subprocess.run([str(x) for x in parts],check=True)
    aapt=tools/('aapt2.exe' if os.name=='nt' else 'aapt2');align=tools/('zipalign.exe' if os.name=='nt' else 'zipalign')
    sources=sorted((root/'app/src/main/java').rglob('*.java'))
    run('java','-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-source','17','-target','17',
        '-classpath',sdk,'-d',classes,*sources)
    with zipfile.ZipFile(build/'classes.jar','w') as archive:
        for path in classes.rglob('*.class'):archive.write(path,path.relative_to(classes).as_posix())
    run('java','-cp',tools/'lib/d8.jar','com.android.tools.r8.D8','--lib',sdk,'--min-api','28','--output',dex,build/'classes.jar')
    ET.register_namespace('android','http://schemas.android.com/apk/res/android')
    manifest=ET.parse(root/'app/src/main/AndroidManifest.xml');manifest.getroot().set('package','pe.bodegamarga.avisos')
    manifest.write(build/'AndroidManifest.xml',encoding='utf-8',xml_declaration=True)
    run(aapt,'compile','--dir',root/'app/src/main/res','-o',build/'resources.zip')
    run(aapt,'link','-I',sdk,'--manifest',build/'AndroidManifest.xml','--min-sdk-version','28','--target-sdk-version','35',
        '--version-code','2','--version-name','0.2-piloto','-o',build/'unsigned.apk',build/'resources.zip')
    with zipfile.ZipFile(build/'unsigned.apk','a') as archive:
        for path in dex.glob('*.dex'):archive.write(path,path.name)
    run(align,'-f','4',build/'unsigned.apk',build/'aligned.apk')
    # Firma de piloto local. La clave privada permanece en build/, excluida del repositorio.
    key=build/'piloto.keystore'
    if not key.exists():
        run('keytool','-genkeypair','-keystore',key,'-storepass','android','-keypass','android','-alias','piloto',
            '-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=Bodega Marga Piloto, O=Desarrollo, C=PE')
    output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    run('java','-jar',tools/'lib/apksigner.jar','sign','--ks',key,'--ks-key-alias','piloto','--ks-pass','pass:android',
        '--key-pass','pass:android','--out',output,build/'aligned.apk')
    run('java','-jar',tools/'lib/apksigner.jar','verify','--verbose',output)
    sha=hashlib.sha256(output.read_bytes()).hexdigest()
    report={'archivo':output.name,'bytes':output.stat().st_size,'sha256':sha,'compile_sdk':35,'target_sdk':35,'min_sdk':28,
            'version':'0.2-piloto','fuentes_java':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            'firma_verificada':True,'probado_en_telefono_fisico':False}
    (output.parent/(output.stem+'_verificacion.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'apk':str(output),'sha256':sha,'bytes':output.stat().st_size}),flush=True)


if __name__=='__main__':main()

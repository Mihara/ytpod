# -*- mode: python -*-

block_cipher = None

a = Analysis(['ytpod.py'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=[
                 'feedgen.ext',
                 'feedgen.ext.podcast',
                 'feedgen.ext.podcast_entry',
                 'feedgen.ext.syndication',
                 'feedgen.ext.dc',
                 'feedgen.ext.media',
                 'feedgen.ext.torrent'
             ],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='ytpod',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True )

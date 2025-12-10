@echo off
echo Создание тестовых VFS структур...

REM Создаем simple структуру
mkdir vfs_simple 2>nul
echo Simple VFS > vfs_simple/notd
echo file1 > vfs_simple/file1.txt

REM Создаем medium структуру  
mkdir vfs_medium 2>nul
mkdir vfs_medium/docs 2>nul
mkdir vfs_medium/data 2>nul
echo Medium VFS > vfs_medium/notd
echo doc1 > vfs_medium/docs/doc1.txt
echo data1 > vfs_medium/data/info.txt

REM Создаем complex структуру (3+ уровня)
mkdir vfs_complex 2>nul
mkdir vfs_complex/level1 2>nul
mkdir vfs_complex/level1/level2 2>nul
mkdir vfs_complex/level1/level2/level3 2>nul
echo Complex VFS > vfs_complex/notd
echo deep file > vfs_complex/level1/level2/level3/deep.txt

echo Структуры созданы!
pause
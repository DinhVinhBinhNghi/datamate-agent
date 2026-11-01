Windows fix for DataMate Chat 3 Group 4 cache builder.

The previous builder committed the temporary SQLite file but did not close its
connection before os.replace. Windows kept the handle open and raised WinError
32. This patch closes the connection in finally before atomic replace.

Install from PowerShell after extracting:

  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Then rerun the Group 4 benchmark command. The old .tmp file is an incomplete
derived cache and can be removed safely before retrying:

  Remove-Item D:\ZALO\data\cache\train\biz_116\sales_lines\*.tmp -Force

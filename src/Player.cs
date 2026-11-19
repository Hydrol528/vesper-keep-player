using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
class Player : Form {
 const string Url="http://127.0.0.1:8097/";
 Process service; Label state; Button open; string root=AppDomain.CurrentDomain.BaseDirectory;
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr OpenEvent(uint access,bool inherit,string name);
 [DllImport("kernel32.dll")] static extern bool SetEvent(IntPtr h);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 static bool Occupied(){try{using(var c=new TcpClient()){c.Connect("127.0.0.1",8097);return true;}}catch{return false;}}
 [STAThread] static int Main(string[] args){
  if(args.Length>0&&args[0]=="--self-test"){
   try {var p=Process.Start(new ProcessStartInfo(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"VesperService.exe"),"--self-test"){UseShellExecute=false,CreateNoWindow=true});if(!p.WaitForExit(30000)){p.Kill();return 2;}return p.ExitCode;}catch{return 3;}
  }
  bool first;using(var mutex=new Mutex(true,"Local\\VesperKeepPlayer.Desktop",out first)){
   if(!first){MessageBox.Show("Vesper Keep Player is already open. Use its window to open your player page.","Vesper Keep Player");return 0;}
   Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new Player());return 0;
  }
 }
 Player(){
  Text="Vesper Keep Player";ClientSize=new Size(640,470);FormBorderStyle=FormBorderStyle.FixedSingle;MaximizeBox=false;StartPosition=FormStartPosition.CenterScreen;BackColor=Color.FromArgb(13,19,28);ForeColor=Color.FromArgb(237,240,245);Font=new Font("Segoe UI",11);
  Icon=new Icon(Path.Combine(root,"vesper.ico"));
  Controls.Add(new PictureBox{Image=Image.FromFile(Path.Combine(root,"vesper-app-icon.png")),SizeMode=PictureBoxSizeMode.Zoom,Bounds=new Rectangle(28,25,65,80)});
  Controls.Add(new Label{Text="VESPER KEEP PLAYER",Font=new Font("Georgia",22),ForeColor=Color.FromArgb(213,178,113),AutoSize=false,Bounds=new Rectangle(108,42,510,45)});
  Controls.Add(new Label{Text="1. Keep Jellyfin Server running.\n2. Open your player page and connect your library.\n3. Pair with the Keep in VRChat and choose what to watch.",Bounds=new Rectangle(30,130,580,100)});
  state=new Label{Text="Starting your player…",ForeColor=Color.FromArgb(145,214,237),Bounds=new Rectangle(30,240,580,62)};Controls.Add(state);
  open=new Button{Text="Open player",Bounds=new Rectangle(30,320,170,45),Enabled=false,BackColor=Color.FromArgb(213,178,113),ForeColor=Color.Black,FlatStyle=FlatStyle.Flat};open.Click+=(s,e)=>Process.Start(new ProcessStartInfo(Url){UseShellExecute=true});Controls.Add(open);
  var help=new Button{Text="How to use",Bounds=new Rectangle(215,320,170,45)};help.Click+=(s,e)=>Process.Start(new ProcessStartInfo(Path.Combine(root,"Start here.html")){UseShellExecute=true});Controls.Add(help);
  var close=new Button{Text="Stop and exit",Bounds=new Rectangle(400,320,200,45)};close.Click+=(s,e)=>Close();Controls.Add(close);
  Controls.Add(new Label{Text="Keep this app and Jellyfin Server running while watching.\nClosing Vesper disconnects its player. Your movies stay in Jellyfin.",Bounds=new Rectangle(30,390,580,55),Font=new Font("Segoe UI",10)});
  Shown+=(s,e)=>StartService();FormClosing+=(s,e)=>StopService();
 }
 void StartService(){
  if(Occupied()){state.Text="Another player is using this connection. Close the existing Vesper player, then reopen this app.";return;}
  try{
   var info=new ProcessStartInfo(Path.Combine(root,"VesperService.exe")){UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=root};info.EnvironmentVariables["VESPER_DATA_DIR"]=Path.Combine(root,"Data");service=Process.Start(info);
   var timer=new System.Windows.Forms.Timer{Interval=300};int ticks=0;timer.Tick+=(s,e)=>{
    if(service.HasExited){timer.Stop();timer.Dispose();state.Text="The player could not start. Check that its installation folder is writable, then reopen the app.";return;}
    if(Occupied()){timer.Stop();timer.Dispose();open.Enabled=true;state.Text="Ready. Open your player page to connect Jellyfin.";return;}
    if(++ticks>100){timer.Stop();timer.Dispose();state.Text="The player is taking longer than expected. Close and reopen the app.";}
   };timer.Start();
  }catch{state.Text="The player could not start. Try repairing the installation in Windows Settings → Apps.";}
 }
 void StopService(){
  if(service==null)return;
  try{if(service.HasExited)return;var h=OpenEvent(2,false,"Local\\VesperKeepPlayer.Stop."+service.Id);if(h!=IntPtr.Zero){SetEvent(h);CloseHandle(h);}if(!service.WaitForExit(5000))service.Kill();}catch{}finally{service.Dispose();}
 }
}
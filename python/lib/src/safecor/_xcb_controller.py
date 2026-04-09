import xcffib
import xcffib.xproto as xproto
from . import SysLogger, SingletonMeta

class XcbController(metaclass=SingletonMeta):
    """ This class provides functions to manipulate the GUI on the system screen 
    
    It does not handle multiple screen.

    This class is a Singleton as it needs to maintain a constant connection to the
    XCB API, because the calls are asynchronous.
    """

    __conn = None
    __current_gui = 0

    def __get_connection(self):
        if self.__conn is None:
            self.__conn = xcffib.connect()

        return self.__conn

    def get_gui_list(self, autoclose = True):
        """ Returns the list of Graphical interfaces visible or hidden """

        gui_list = {}

        conn = self.__get_connection()

        setup = conn.get_setup()
        if len(setup.roots) == 0:
            SysLogger("XcbHelper").warn("No screen found")
            return
        
        screen = setup.roots[0]
        root = screen.root

        tree = conn.core.QueryTree(root).reply()
        windows = tree.children
        atom_wm_name = conn.core.InternAtom(False, len("WM_NAME"), "WM_NAME").reply().atom

        for win in windows:
            prop = conn.core.GetProperty(False, win, atom_wm_name, xproto.GetPropertyType.Any, 0, 1024).reply()
            name = prop.value.to_string()
            if name.startswith("QEMU ("):
                # Extract the Domain name from the window name
                domain_name = name.split("(")[1].split(")")[0]
                gui_list[domain_name] = win

        return gui_list

    def hide_gui(self, window_id, conn:xcffib.Connection = None):
        """ Hides the Graphical interface of a Domain """

        conn = self.__get_connection()
        conn.core.UnmapWindow(window_id)
        conn.flush()
        
        #if autoclose is not None:
        #    conn.disconnect()

    def show_gui(self, window_id, full_screen = True, conn:xcffib.Connection = None):
        """ Shows the Graphical interface of a Domain """

        # Set the window fullscreen
        if full_screen:
            screen_size = self.get_screen_size(False)
            self.set_gui_dimensions(
                window_id, 
                0, 
                0, 
                screen_size[0], 
                screen_size[1], 
                False
            )

        # Show the window
        SysLogger("XcbController").info(f"Show window {window_id}")
        conn = self.__get_connection()
        conn.core.MapWindow(window_id)
        conn.flush()
       
    def set_gui_dimensions(self, window_id, x:int, y:int, width:int, height:int, conn:xcffib.Connection = None):
        """ Sets the dimensions and position of a Graphical interface """

        mask = (
            xproto.ConfigWindow.X |
            xproto.ConfigWindow.Y |
            xproto.ConfigWindow.Width |
            xproto.ConfigWindow.Height
        )        

        values = [x, y, width, height]

        conn = self.__get_connection()
        conn.core.ConfigureWindow(window_id, mask, values)
        conn.flush()

    def get_screen_size(self, conn:xcffib.Connection = None) -> tuple[int, int]:
        """ Gets the screen size (width, height )"""

        conn = self.__get_connection()
        setup = conn.get_setup()
        roots = setup.roots

        if len(setup.roots) == 0:
            SysLogger("XcbHelper").warn("No screen found")
            return
        
        screen = roots[0]
        width = screen.width_in_pixels
        height = screen.height_in_pixels
     
        return width, height
    
    def get_current_gui(self) -> int:
        """ Finds the currently visible Graphical Interface """

        conn = self.__get_connection()

        windows = self.get_gui_list()

        for domain_name, win_id in windows.items():
            attrs = conn.core.GetWindowAttributes(win_id).reply()
            if attrs.map_state == xproto.MapState.Viewable:
                return domain_name, win_id
        
        return "", 0

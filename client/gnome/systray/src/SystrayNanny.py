#!/usr/bin/env python

# Copyright (C) 2009,2010 Junta de Andalucia
# 
# Authors:
#   Roberto Majadas <roberto.majadas at openshine.com>
#   Cesar Garcia Tapia <cesar.garcia.tapia at openshine.com>
#   Luis de Bethencourt <luibg at openshine.com>
#   Pablo Vieytes <pvieytes at openshine.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
# USA

import os
import os.path

import gtk
if os.name == "posix" :
    import pynotify
elif os.name == "nt":
    import nanny.daemon.Win32UsersManager
    import getpass
    from gtkPopupNotify import NotificationStack

import gobject
from gettext import ngettext

import nanny.client.common
import nanny.client.gnome.systray
import gettext

ngettext = gettext.ngettext


class SystrayNanny(gtk.StatusIcon):
    def __init__(self):
        #atributes
        self.times_left = { 0:[-1, False], 1:[-1, False], 2:[-1, False] , 3:[-1, False] }
        self.times_show = { 0:-1, 1:-1, 2:-1, 3:-1 }
        self.app_names = { 0: _("Session"),
                           1: _("Web browser"),
                           2: _("e-Mail"),
                           3: _("Instant messanger")
                         }
        self.look_times = [ 60, 30, 15, 5, 4, 3, 2, 1 ]
        
        #systray
        gtk.StatusIcon.__init__ (self)
        icon_path = os.path.join (nanny.client.gnome.systray.icons_files_dir, "24x24/apps", "nanny.png")
        self.set_from_file(icon_path)
        self.set_visible(False)
        self.set_tooltip("")
        self.last_tooltip = ''

        #dbus
        self.dbus = nanny.client.common.DBusClient()
        
        if os.name == "nt":
            users_manager = nanny.daemon.Win32UsersManager.Win32UsersManager()
            self.uid = ''
            for uid, username, desc in users_manager.get_users() :
                if username == getpass.getuser() :
                    self.uid = uid
                    break
            gobject.timeout_add(1000, self.__block_status_windows_polling)
            self.win_notify = NotificationStack()

        elif os.name == "posix":
            self.dbus.connect("user-notification", self.__handlerUserNotification)

        #timer
        gobject.timeout_add(3000, self.__handlerTimer )

    def __block_status_windows_polling(self):
        ret = self.dbus.get_block_status_by_uid(self.uid)
        for k in ret.keys():
            block_status = ret[k][0]
            user_id = self.uid
            app_id = k
            next_change = ret[k][1]
            available_time = ret[k][2]
            self.__handlerUserNotification(self.dbus,  block_status, 
                                           user_id, app_id, 
                                           next_change, available_time)
        
        return True

    def __handlerUserNotification(self, dbus, block_status, user_id, app_id, next_change, available_time):
        if os.name == "posix" :
            uid= str(os.getuid())
        elif os.name == "nt":
            uid = self.uid

        if uid==user_id:
            self.times_left[app_id] = [next_change, block_status]


    def __handlerTimer(self):
        mssg=""
        mssg_ready=False
        for app_id in self.times_left:
            if self.times_left[app_id][0]!=-1:
                if self.times_show[app_id] == -1:
                    self.times_show[app_id] = self.times_left[app_id][0] + 60 

                for time in self.look_times:
                    #first element
                    if time == self.look_times[0]:
                        if self.times_left[app_id][0] >= time and self.times_show[app_id]-self.times_left[app_id][0] >= time:
                            self.times_show[app_id]=self.times_left[app_id][0]
                            mssg_ready=True
                    else:
                        if self.times_left[app_id][0]<= time and self.times_show[app_id]-self.times_left[app_id][0] >= time:
                            self.times_show[app_id]=self.times_left[app_id][0]
                            mssg_ready=True

                time = self.__format_time (self.times_left[app_id][0])
                if len (mssg) > 0:
                    mssg += "\n"
                if self.times_left[app_id][1]:
                    # To translators: In x-minutes the access to <app> will be granted
                    mssg += _("In %(time)s the access to %(app)s will be granted.") % {'time': time, 'app': self.app_names[app_id]}
                else:
                    # To translators: In x-minutes the access to <app> will be denied
                    mssg += _("In %(time)s the access to %(app)s will be denied.") % {'time': time, 'app': self.app_names[app_id]}

        if mssg_ready:
            self.__showNotification( mssg )
        
        if self.last_tooltip != mssg : 
            self.set_tooltip( mssg )
            self.last_tooltip = mssg
            print mssg
        
        if len(mssg) != 0 :
            self.set_visible(True)
        else:
            self.set_visible(False)

        return True

    def __format_time (self, minutes):
        h, m = divmod(minutes, 60)
        d, h = divmod (h, 24)

        time_list = []
        if d > 0:
            time_list.append(ngettext("%d day", "%d days", d) % d)
        if h > 0:
            time_list.append(ngettext("%d hour", "%d hours", h) % h)
        if m > 0:
            time_list.append(ngettext("%d minute", "%d minutes", m) % m)
        # Translators: This is the separator between time strings, like '1 day, 2 hours, 3 minutes'
        time = _(", ").join(time_list)

        return time

    def __showNotification (self, mssg):
        icon_path = os.path.join (nanny.client.gnome.systray.icons_files_dir, "48x48/apps", "nanny.png")

        if os.name == "posix":
            pynotify.init ("aa")
            self.notificacion = pynotify.Notification ("Nanny", mssg, icon_path)
            self.notificacion.show()
        elif os.name == "nt":
            self.win_notify.new_popup("Nanny", mssg, icon_path)

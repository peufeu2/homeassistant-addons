#!/usr/bin/python
# -*- coding: utf-8 -*-

#   Mixin to add to classes to persist states
#   Class must have .api, 
#
class PersistMixin:
    def _save( self, state, attrs ):
        if not self.entity_storage_id:
            return
        try:
            old_namespace = self.api.get_namespace()
            self.api.set_namespace( "userapps" )
            self.api.set_state( self.entity_storage_id, state=state, attributes = attrs )
        finally:
            self.api.set_namespace( old_namespace )

    def _load( self ):
        if not self.entity_storage_id:
            return None, {}
        try:
            old_namespace = self.api.get_namespace()
            self.api.set_namespace( "userapps" )
            # self.api.log( "Loading %s", self.entity_storage_id )
            d = self.api.get_state( self.entity_storage_id, attribute="all", default={} )
            self.debug( "Loading %s: %s", self.entity_storage_id, d )
            if not d:
                self.debug( "Creating entity %s", self.entity_storage_id )
                ent = self.api.get_entity( self.entity_storage_id )
                # ent.add( state = "off" )
                ent.add()
                return None, {}
            return d["state"], d["attributes"]
        finally:
            self.api.set_namespace( old_namespace )
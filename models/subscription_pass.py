import xmlrpc.client
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError

class SubscriptionPass(models.Model):
    _name = 'anpr.subscription.pass'
    _description = 'Abonnement Péage'

    name = fields.Char(string="Nom de l'abonné", required=True)
    plate = fields.Char(string="Plaque d'immatriculation", required=True, index=True)
    vehicle_type = fields.Selection([
        ('car', 'Car'),
        ('4x4', '4x4 / SUV'),
        ('bus', 'Bus'),
        ('camion', 'Camion'),
        ('autres', 'Autres'),
    ], string="Type de véhicule", required=True)
    balance = fields.Float(string="Solde du compte", required=True, default=0.0)
    cost_per_passage = fields.Float(string="Coût par passage", required=True, default=500.0)

    remote_id = fields.Integer(string="ID sur le serveur distant")
    is_remote = fields.Boolean(string="Synchronisé avec serveur distant", default=False)
    last_sync_date = fields.Datetime(string="Dernière synchronisation")

    def debit_passage(self):
        """Déduit le coût du passage et synchronise"""
        for rec in self:
            if rec.balance >= rec.cost_per_passage:
                rec.balance -= rec.cost_per_passage
                if rec.is_remote:
                    rec.sync_to_remote()
            else:
                raise UserError("Solde insuffisant pour ce passage.")

    def _get_remote_connection(self):
        """Récupère la configuration depuis le modèle dédié"""
        config = self.env['anpr.subscription.config'].get_config()
        if not config:
            raise UserError(
                "Configuration des abonnements non trouvée.\n"
                "Veuillez configurer les paramètres dans:\n"
                "Abonnements ANPR → Configuration ANPR"
            )
        
        return {
            'url': config.remote_odoo_url,
            'db': config.remote_odoo_db,
            'login': config.remote_odoo_login,
            'password': config.remote_odoo_password,
            'prefix': config.remote_odoo_prefix
        }

    def _authenticate_remote(self, conn):
        common = xmlrpc.client.ServerProxy(f"{conn['url'].rstrip('/')}/xmlrpc/2/common")
        uid = common.authenticate(conn['db'], conn['login'], conn['password'], {})
        if not uid:
            raise Exception("Échec d’authentification sur le serveur distant.")
        return uid

    def sync_all_from_remote(self):
        conn = self._get_remote_connection()
        uid = self._authenticate_remote(conn)
        models = xmlrpc.client.ServerProxy(f"{conn['url'].rstrip('/')}/xmlrpc/2/object")

        # Ajouter cost_per_passage dans les champs lus du serveur distant
        remote_records = models.execute_kw(conn['db'], uid, conn['password'],
                                          'anpr.subscription.pass', 'search_read',
                                          [[]], {'fields': ['id', 'name', 'plate', 'vehicle_type', 'balance', 'cost_per_passage']})

        for rec in remote_records:
            local = self.search([('plate', '=', rec['plate'])], limit=1)
            vals = {
                'name': rec['name'],
                'plate': rec['plate'],
                'vehicle_type': rec['vehicle_type'],
                'balance': rec['balance'],
                'cost_per_passage': rec.get('cost_per_passage', 500.0),
                'remote_id': rec['id'],
                'is_remote': True,
                'last_sync_date': fields.Datetime.now(),
            }
            if local:
                local.write(vals)
            else:
                self.create(vals)

    def sync_to_remote(self):
        conn = self._get_remote_connection()
        uid = self._authenticate_remote(conn)
        models = xmlrpc.client.ServerProxy(f"{conn['url'].rstrip('/')}/xmlrpc/2/object")

        for rec in self.search([('is_remote', '=', False)]):
            vals = {
                'name': rec.name,
                'plate': rec.plate,
                'vehicle_type': rec.vehicle_type,
                'balance': rec.balance,
                'cost_per_passage': rec.cost_per_passage,
            }
            remote_id = models.execute_kw(conn['db'], uid, conn['password'],
                                          'anpr.subscription.pass', 'create', [vals])
            rec.write({
                'remote_id': remote_id,
                'is_remote': True,
                'last_sync_date': fields.Datetime.now(),
            })

    @api.model
    def cron_sync_abonnements(self):
        self.sync_to_remote()
        self.sync_all_from_remote()
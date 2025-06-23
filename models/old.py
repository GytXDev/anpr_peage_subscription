from odoo import models, fields, api, http
from odoo.exceptions import UserError
import requests
import json
from datetime import datetime, timedelta

class SubscriptionPass(models.Model):
    _name = 'anpr.subscription.pass'
    _description = 'Abonnement Péage'
    _order = 'last_sync_date desc'

    name = fields.Char(string="Nom de l'abonné", required=True)
    plate = fields.Char(string="Plaque d'immatriculation", required=True, index=True)
    vehicle_type = fields.Selection([
        ('car',     'Car'),
        ('4x4',     '4x4 / SUV'),
        ('bus',     'Bus'),
        ('camion',  'Camion'),
        ('autres',  'Autres'),
    ], string="Type de véhicule", required=True)
    balance = fields.Float(string="Solde du compte", required=True, default=0.0)
    cost_per_passage = fields.Float(string="Coût par passage", required=True, default=500.0)
    
    # Synchronisation fields
    is_remote = fields.Boolean(string="Synchronisé avec le serveur distant")
    remote_id = fields.Integer(string="ID sur le serveur distant")
    last_sync_date = fields.Datetime(string="Dernière synchronisation")
    sync_origin = fields.Selection([
        ('local', 'Local'),
        ('remote', 'Distant')
    ], string="Origine de la synchronisation")

    def get_remote_connection(self):
        """Récupère les paramètres de connexion au serveur distant"""
        user = http.request.env.user
        return {
            'url': user.remote_odoo_url,
            'db': user.remote_odoo_db,
            'login': user.remote_odoo_login,
            'password': user.remote_odoo_password
        }

    def _call_remote_api(self, model, method, args, kwargs=None):
        """Méthode générique pour appeler l'API distante"""
        conn = self.get_remote_connection()
        if not all(conn.values()):
            raise UserError("Configuration de connexion distante incomplète")

        url = f"{conn['url']}/web/dataset/call_kw/{model}/{method}"
        headers = {'Content-Type': 'application/json'}
        data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": method,
                "args": args,
                "kwargs": kwargs or {},
            },
            "id": 1,
        }

        try:
            response = requests.post(
                url,
                data=json.dumps(data),
                headers=headers,
                auth=(conn['login'], conn['password']),
                timeout=10)
            
            if response.status_code == 200:
                return response.json().get('result')
            else:
                raise UserError(f"Erreur API distante: {response.text}")
        except Exception as e:
            raise UserError(f"Erreur de connexion au serveur distant: {str(e)}")

    def find_local_by_plate(self, plate):
        """Trouve un abonnement local par plaque"""
        return self.search([('plate', '=', plate)], limit=1)

    def sync_from_remote(self, remote_record):
        """Synchronise un enregistrement local à partir des données distantes"""
        vals = {
            'name': remote_record['name'],
            'plate': remote_record['plate'],
            'vehicle_type': remote_record['vehicle_type'],
            'balance': remote_record['balance'],
            'is_remote': True,
            'remote_id': remote_record['id'],
            'last_sync_date': fields.Datetime.now(),
            'sync_origin': 'remote'
        }
        
        local_record = self.find_local_by_plate(remote_record['plate'])
        if local_record:
            local_record.write(vals)
        else:
            vals.update({'cost_per_passage': 500.0})  # Valeur par défaut locale
            self.create(vals)

    def sync_to_remote(self):
        """Synchronise l'enregistrement local vers le serveur distant"""
        for rec in self:
            if rec.sync_origin == 'remote':
                continue  # Ne pas resynchroniser ce qui vient du distant

            remote_vals = {
                'name': rec.name,
                'plate': rec.plate,
                'vehicle_type': rec.vehicle_type,
                'balance': rec.balance,
                'cost_per_passage': 0,  # Pas de facturation sur le distant
            }

            if rec.is_remote and rec.remote_id:
                # Mise à jour de l'existant
                self._call_remote_api(
                    'anpr.subscription.pass',
                    'write',
                    [[rec.remote_id], remote_vals])
            else:
                # Création d'un nouveau
                remote_id = self._call_remote_api(
                    'anpr.subscription.pass',
                    'create',
                    [remote_vals])
                
                if remote_id:
                    rec.write({
                        'is_remote': True,
                        'remote_id': remote_id,
                        'last_sync_date': fields.Datetime.now(),
                        'sync_origin': 'local'
                    })

    @api.model
    def sync_all_from_remote(self):
        """Synchronise tous les abonnements depuis le serveur distant"""
        remote_records = self._call_remote_api(
            'anpr.subscription.pass',
            'search_read',
            [[]],
            {'fields': ['id', 'name', 'plate', 'vehicle_type', 'balance', 'write_date']})
        
        for remote_record in remote_records:
            self.sync_from_remote(remote_record)

    @api.model
    def create(self, vals):
        """Override de la création pour synchroniser vers le distant"""
        record = super(SubscriptionPass, self).create(vals)
        if not record.get('sync_origin') == 'remote':
            record.sync_to_remote()
        return record

    def write(self, vals):
        """Override de l'écriture pour synchroniser vers le distant"""
        # Exclure les champs techniques de la synchronisation
        sync_vals = {k: v for k, v in vals.items() 
                    if k not in ['is_remote', 'remote_id', 'last_sync_date', 'sync_origin']}
        
        result = super(SubscriptionPass, self).write(vals)
        
        if sync_vals:
            for rec in self:
                if rec.is_remote and rec.sync_origin == 'local':
                    rec.sync_to_remote()
        return result

    def debit_passage(self):
        """Déduit le coût du passage et synchronise"""
        for rec in self:
            if rec.balance >= rec.cost_per_passage:
                rec.balance -= rec.cost_per_passage
                if rec.is_remote and rec.sync_origin == 'local':
                    rec.sync_to_remote()
            else:
                raise UserError("Solde insuffisant pour ce passage.")

    @api.model
    def cron_sync_abonnements(self):
        """Méthode planifiée pour la synchronisation automatique"""
        # Synchroniser les modifications locales vers le distant
        local_updates = self.search([
            ('is_remote', '=', True),
            ('sync_origin', '=', 'local'),
            ('last_sync_date', '<', fields.Datetime.now() - timedelta(minutes=5))
        ])
        local_updates.sync_to_remote()

        # Synchroniser les modifications distantes vers le local
        self.sync_all_from_remote()
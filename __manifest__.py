{
    'name': "Abonnement Péage",
    'summary': "Gestion des abonnements pour le péage automatique",
    'author': "Ogooué Technologies",
    'category': 'Custom',
    'version': '1.0',
    'depends': ['base'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/subscription_pass_views.xml',
    ],
    'installable': True,
    'application': True,
}

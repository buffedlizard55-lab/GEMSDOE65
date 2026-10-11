import numpy as np
from gems65.canary import feature_canaries


def test_canary_catches_direct_and_inverse_leakage():
    truth=np.r_[np.zeros(40),np.ones(40)]
    bank=np.array([truth,1-truth]).reshape(2,8,10)
    train=np.column_stack([np.arange(20),np.arange(20)])
    rows=feature_canaries(train,np.ones(20)/20,bank,np.arange(80),truth,['leak','inverse'],0)
    raw=[r for r in rows if r['transform']=='imputed_raw']
    assert all(not r['passed'] and r['max_direction_auc']==1 for r in raw)


def test_quadratic_canary_catches_u_shaped_feature():
    z=np.r_[np.linspace(-3,-2,25),np.linspace(-1,1,50),np.linspace(2,3,25)]
    truth=(abs(z)>1.5)
    bank=z.reshape(1,10,10);train=z.reshape(-1,1)
    rows=feature_canaries(train,np.ones(100)/100,bank,np.arange(100),truth,['u'],1)
    assert rows[0]['passed']
    assert not rows[2]['passed']

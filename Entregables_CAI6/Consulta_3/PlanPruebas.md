# Plan de pruebas - HealthProcurementAuction

## 1. Pruebas estaticas (pre-despliegue)

### 1.1 Slither
Comando: `slither contracts/HealthProcurementAuction.sol --solc-remaps '@openzeppelin/=node_modules/@openzeppelin/'`

Hallazgos esperados y mitigacion:
| Detector | Severidad | Estado |
|----------|-----------|--------|
| timestamp | Low | Aceptado: requisito de subasta exige `block.timestamp` |
| reentrancy-eth | Critical | Mitigado: `nonReentrant` + checks-effects-interactions |
| arbitrary-send | High | Falso positivo: pagos limitados a winner / healthService |
| missing-zero-check | Medium | Mitigado: `_healthService != address(0)` |
| solc-version | Informational | Aceptado: pragma 0.8.20 (>=0.8.0 protege overflow) |

### 1.2 Mythril
Comando: `myth analyze contracts/HealthProcurementAuction.sol --solv 0.8.24`

Hallazgos esperados:
- SWC-107 reentrancy: no aplica (mitigado).
- SWC-101 integer over/underflow: protegido por Solidity 0.8.
- SWC-105 unprotected ether withdrawal: no aplica (`onlyHealthService` y `winner`).
- SWC-110 assert violation: no aplica.

### 1.3 Solhint
Comando: `npm run static:solhint`
Resultado esperado: 0 errores. Las advertencias son de estilo, NatSpec u optimizacion de gas; no bloquean el comportamiento funcional.

## 2. Pruebas dinamicas (Hardhat local)

Ejecutar: `npm install && npm test`

Casos cubiertos por `test/HealthProcurementAuction.test.js`:
1. Rechazo de deposito 0 al hacer commit.
2. Rechazo de doble commit por el mismo wallet.
3. Rechazo de reveal con puja superior al `maxAcceptablePrice`.
4. Rechazo de reveal con deposito inferior al 10% de la puja.
5. Calculo correcto del ganador (puja minima) y segundo precio distinto.
6. Caso unica puja: pago a precio propio.
7. No ganadores recuperan deposito.
8. Ganador no puede usar `withdrawDeposit` (flujo de entrega).
9. Pago al ganador en `confirmDeliveryAndPay` por segundo precio + reembolso de deposito.
10. Penalizacion por no entrega: deposito retenido para `healthService`.
11. Cierre por `MAX_BIDS = 30`.
12. Bloqueo de `finalizeAuction` antes de `revealDeadline` y control `onlyHealthService`.
13. Publicacion de todas las pujas reveladas solo despues de finalizar.
14. Factory crea subastas independientes con parametros distintos.

## 3. Pruebas dinamicas (Sepolia testnet)

### Preparacion
1. `cp .env.example .env` y completar `PRIVATE_KEY`, `SEPOLIA_RPC_URL`, `ETHERSCAN_API_KEY`.
2. Conectar MetaMask a Sepolia.
3. Conseguir ETH de prueba en faucet (https://sepoliafaucet.com o google faucet).

### Despliegue
```
npm run compile
npm run deploy:sepolia
```

### Verificacion en Etherscan
```
npx hardhat verify --network sepolia <factoryAddress>
npx hardhat verify --network sepolia <auctionAddress> <healthService> <auctionStart> <biddingDeadline> <revealDeadline> <deliveryDeadline> <maxPrice>
```

### Suite de operaciones a registrar
| ID | Operacion | Cuenta | Esperado |
|----|-----------|--------|----------|
| OP1 | `commitBid(hash, deposit)` | proveedor1 | tx OK, evento `BidCommitted` |
| OP2 | `commitBid` mismo wallet | proveedor1 | revert "Bidder already committed" |
| OP3 | `revealBid(amount, secret)` | proveedor1 | tx OK, evento `BidRevealed` |
| OP4 | `revealBid` con amount > maxPrice | proveedor2 | revert "Bid exceeds max price" |
| OP5 | `finalizeAuction` antes de revealDeadline | health | revert "Reveal phase not ended" |
| OP6 | `finalizeAuction` post reveal | health | tx OK, evento `AuctionFinalized` |
| OP7 | `withdrawDeposit` no ganador | proveedor2 | tx OK, evento `DepositWithdrawn` |
| OP8 | `confirmDeliveryAndPay` con value=secondPrice | health | tx OK, evento `DeliveryConfirmed` |
| OP9 | `markNonDelivery` post deliveryDeadline | health | tx OK, evento `WinnerPenalized` |

Cada hash de transaccion se documentara en una tabla con enlace a `https://sepolia.etherscan.io/tx/<hash>` como evidencia auditable.

## 4. Cobertura cruzada con requisitos

| Requisito CAI 6.3 | Cubierto por |
|-------------------|--------------|
| Pujas confidenciales hasta cierre | Commit-reveal (`commitBid` / `revealBid`) |
| Cierre por 30 pujas o deadline | `MAX_BIDS` + `commitClosed` |
| Una sola puja por wallet | `bidders[msg.sender].committed` |
| Puja entera positiva | `_amount > 0` |
| Maximo aceptable | `_amount <= maxAcceptablePrice` |
| Ganador puja minima, paga segundo precio | `finalizeAuction` |
| Empate: gana el primero | `commitOrder` |
| Caso unica puja: pago propio precio | `secondDistinct == max ? bestAmount : ...` |
| Deposito 10% al pujar | `b.deposit * 10 >= _amount` |
| Devolucion deposito a no ganadores | `withdrawDeposit` |
| Devolucion deposito + pago al ganador entregado | `confirmDeliveryAndPay` |
| Retencion deposito si no entrega | `markNonDelivery` |
| Conocer ganador y todas las pujas | `getAllRevealedBids`, `winner`, `priceToPay` |
| Reusabilidad ilimitada del contrato | `HealthProcurementAuctionFactory` |
| Resistencia a ataques conocidos | `nonReentrant`, CEI, `onlyHealthService`, Solidity 0.8 |

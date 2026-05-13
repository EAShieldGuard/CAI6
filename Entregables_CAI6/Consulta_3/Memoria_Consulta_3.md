# Resolucion tecnica - Consulta 6.3 (Accountability en compras con blockchain)

## 1. Contrato implementado y cobertura de requisitos
Archivo principal: `HealthProcurementAuction.sol`

Contratos:
1. `HealthProcurementAuction`: subasta Vickrey inversa con commit-reveal.
2. `HealthProcurementAuctionFactory`: instanciacion ilimitada con parametros independientes (auctionStart, biddingDeadline, revealDeadline, deliveryDeadline, maxAcceptablePrice).

Cobertura funcional verificada:
- Commit-reveal -> confidencialidad de pujas hasta el cierre.
- Cierre por `MAX_BIDS = 30` o por `biddingDeadline`.
- Una sola puja por wallet (`bidders[msg.sender].committed`).
- Puja entera > 0 y <= `maxAcceptablePrice`.
- Deposito >= 10% de la puja (`b.deposit * 10 >= _amount`).
- Ganador: puja minima; en empate gana quien comprometio antes (`commitOrder`).
- Pago al ganador: segundo precio distinto mas bajo (o precio propio si no existe segundo).
- Devolucion de deposito a no ganadores (`withdrawDeposit`).
- Pago al ganador en `confirmDeliveryAndPay` (msg.value = priceToPay) y reembolso de su deposito.
- Retencion del deposito si no entrega (`markNonDelivery`) y transferencia al `healthService`.
- Auditabilidad: `getAllRevealedBids`, `winner`, `priceToPay` y eventos por accion critica.

## 2. Medidas de seguridad aplicadas
1. `nonReentrant` en funciones de transferencia.
2. Checks-Effects-Interactions antes de cada `call`.
3. Validacion estricta de fases temporales (`commitClosed`, `revealOpen`, `block.timestamp > revealDeadline`).
4. `onlyHealthService` en `finalizeAuction`, `confirmDeliveryAndPay`, `markNonDelivery`.
5. Solidity 0.8.20 con proteccion intrinseca de over/underflow.
6. Eventos para trazabilidad on-chain (`BidCommitted`, `BidRevealed`, `AuctionFinalized`, `DepositWithdrawn`, `DeliveryConfirmed`, `WinnerPenalized`, `AuctionCreated`).

## 3. Testing estatico
Script: `scripts/static_analysis.sh` ejecuta:
- Slither -> `reports/slither.{json,txt}`
- Mythril -> `reports/mythril.md`
- Solhint -> `reports/solhint.txt`

Tabla de resultados esperados, severidad y mitigacion en `PlanPruebas.md` seccion 1. Falsos positivos clasicos (timestamp, arbitrary-send) se justifican por requisito. En la revision final, `npm run static:solhint` devuelve 0 errores; las advertencias restantes son de estilo, NatSpec u optimizacion de gas.

## 4. Testing dinamico (Hardhat)
Comandos:
```
cp .env.example .env   # rellenar PRIVATE_KEY, SEPOLIA_RPC_URL, ETHERSCAN_API_KEY
npm install
npm test
```
14 casos automatizados cubren todos los requisitos funcionales y de seguridad (`test/HealthProcurementAuction.test.js`), incluida la publicacion de pujas reveladas mediante `getAllRevealedBids`.

## 5. Despliegue en Sepolia
```
npm run compile
npm run deploy:local
npm run deploy:sepolia
npx hardhat verify --network sepolia <addr> <args...>
```
Justificacion tecnica:
- Sepolia es la testnet PoS oficialmente mantenida; Goerli esta deprecada.
- MetaMask provee firma cliente para usuarios del Servicio de Salud.
- Faucets gratuitos (sepoliafaucet.com, google faucet) para abastecer wallets de prueba.
- Etherscan-Sepolia da evidencia inmutable y auditable (hashes de tx + verificacion de bytecode).

## 6. Plan de pruebas dinamicas en testnet
Detalle completo en `PlanPruebas.md` seccion 3, incluida la matriz de operaciones (OP1-OP9), cuentas, esperado y enlace a evidencia en `https://sepolia.etherscan.io/address/0x97a971333e85B08eB2da2a3ec9c5f11Afb1Ff781`.

## 7. Conexion de usuarios del Servicio de Salud
- Personal del SS: MetaMask -> Sepolia + cuenta importada.
- Proveedores: MetaMask con su wallet corporativa.
- Frontend / DApp (fuera de alcance) interactua via ethers.js usando ABI generado por Hardhat (`artifacts/`).

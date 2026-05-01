// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title HealthProcurementAuction
 * @dev Subasta Vickrey inversa con commit-reveal para compras sanitarias.
 * Requisitos clave cubiertos:
 * - Commit confidencial y reveal posterior.
 * - Maximo de 30 pujas o cierre por deadline.
 * - Ganador: puja mas baja; en empate gana quien comprometio antes.
 * - Pago: segundo precio distinto mas bajo (o propio precio si no existe).
 * - Depositos: devolucion a no ganadores; deposito del ganador retenido
 *   hasta confirmar entrega o penalizacion por no entrega.
 */
contract HealthProcurementAuction {
    uint256 public constant MAX_BIDS = 30;

    address public healthService;
    uint256 public auctionStart;
    uint256 public biddingDeadline;
    uint256 public revealDeadline;
    uint256 public deliveryDeadline;
    uint256 public maxAcceptablePrice;

    struct Bidder {
        bytes32 commitHash;
        uint256 deposit;
        uint256 revealedBid;
        uint64 commitOrder;
        bool committed;
        bool hasRevealed;
        bool depositWithdrawn;
    }

    mapping(address => Bidder) public bidders;
    address[] public bidderAddresses;

    uint256 public totalCommitted;
    uint256 public totalRevealed;

    address public winner;
    uint256 public winningBid;
    uint256 public priceToPay;
    uint256 public winnerLockedDeposit;

    bool public isFinalized;
    bool public deliveryConfirmed;
    bool public winnerPenalized;

    bool private locked;

    event BidCommitted(address indexed bidder, uint256 deposit, uint64 commitOrder);
    event BidRevealed(address indexed bidder, uint256 amount);
    event AuctionFinalized(address indexed winner, uint256 winningBid, uint256 priceToPay);
    event DepositWithdrawn(address indexed bidder, uint256 amount);
    event DeliveryConfirmed(address indexed winner, uint256 totalPayout);
    event WinnerPenalized(address indexed winner, uint256 retainedDeposit);

    modifier onlyHealthService() {
        require(msg.sender == healthService, "Only Health Service can perform this action");
        _;
    }

    modifier nonReentrant() {
        require(!locked, "Reentrancy blocked");
        locked = true;
        _;
        locked = false;
    }

    /**
     * @dev Inicializa una subasta parametrizable.
     * @param _healthService Wallet del Servicio de Salud.
     * @param _auctionStart Timestamp de inicio de commit.
     * @param _biddingDeadline Timestamp de fin de commit.
     * @param _revealDeadline Timestamp de fin de reveal.
     * @param _deliveryDeadline Timestamp limite de entrega.
     * @param _maxPrice Maximo precio aceptable.
     */
    constructor(
        address _healthService,
        uint256 _auctionStart,
        uint256 _biddingDeadline,
        uint256 _revealDeadline,
        uint256 _deliveryDeadline,
        uint256 _maxPrice
    ) {
        require(_healthService != address(0), "healthService required");
        require(_auctionStart < _biddingDeadline, "Invalid bidding range");
        require(_biddingDeadline < _revealDeadline, "Invalid reveal range");
        require(_revealDeadline < _deliveryDeadline, "Invalid delivery range");
        require(_maxPrice > 0, "maxPrice must be > 0");

        healthService = _healthService;
        auctionStart = _auctionStart;
        biddingDeadline = _biddingDeadline;
        revealDeadline = _revealDeadline;
        deliveryDeadline = _deliveryDeadline;
        maxAcceptablePrice = _maxPrice;
    }

    function commitClosed() public view returns (bool) {
        return block.timestamp > biddingDeadline || totalCommitted >= MAX_BIDS;
    }

    function revealOpen() public view returns (bool) {
        return commitClosed() && block.timestamp <= revealDeadline;
    }

    /**
     * @dev Fase commit: registra hash y deposito.
     */
    function commitBid(bytes32 _commitHash) external payable {
        require(block.timestamp >= auctionStart, "Auction not started");
        require(!commitClosed(), "Commit phase closed");
        require(_commitHash != bytes32(0), "Commit hash required");
        require(msg.value > 0, "Deposit must be > 0");
        require(!bidders[msg.sender].committed, "Bidder already committed");

        totalCommitted += 1;
        bidders[msg.sender] = Bidder({
            commitHash: _commitHash,
            deposit: msg.value,
            revealedBid: 0,
            commitOrder: uint64(totalCommitted),
            committed: true,
            hasRevealed: false,
            depositWithdrawn: false
        });
        bidderAddresses.push(msg.sender);

        emit BidCommitted(msg.sender, msg.value, uint64(totalCommitted));
    }

    /**
     * @dev Fase reveal: valida compromiso, deposito y limites de precio.
     */
    function revealBid(uint256 _amount, string memory _secret) external {
        require(revealOpen(), "Reveal phase not available");

        Bidder storage b = bidders[msg.sender];
        require(b.committed, "Bidder did not commit");
        require(!b.hasRevealed, "Ya has revelado tu puja");

        bytes32 computedHash = keccak256(abi.encodePacked(_amount, _secret));
        require(computedHash == b.commitHash, "Commit mismatch");
        require(_amount > 0, "Bid must be > 0");
        require(_amount <= maxAcceptablePrice, "Bid exceeds max price");
        require(b.deposit * 10 >= _amount, "Deposit below required 10%");

        b.revealedBid = _amount;
        b.hasRevealed = true;
        totalRevealed += 1;

        emit BidRevealed(msg.sender, _amount);
    }

    /**
     * @dev Finaliza la subasta y calcula ganador + segundo precio.
     */
    function finalizeAuction() external onlyHealthService {
        require(!isFinalized, "Auction already finalized");
        require(commitClosed(), "Commit phase still open");
        require(block.timestamp > revealDeadline, "Reveal phase not ended");

        address bestBidder = address(0);
        uint256 bestAmount = type(uint256).max;
        uint256 secondDistinct = type(uint256).max;
        uint64 bestOrder = type(uint64).max;

        for (uint256 i = 0; i < bidderAddresses.length; i++) {
            address bidder = bidderAddresses[i];
            Bidder storage b = bidders[bidder];
            if (!b.hasRevealed) {
                continue;
            }

            uint256 amount = b.revealedBid;
            if (amount < bestAmount) {
                secondDistinct = bestAmount;
                bestAmount = amount;
                bestBidder = bidder;
                bestOrder = b.commitOrder;
            } else if (amount == bestAmount) {
                if (b.commitOrder < bestOrder) {
                    bestBidder = bidder;
                    bestOrder = b.commitOrder;
                }
            } else if (amount < secondDistinct) {
                secondDistinct = amount;
            }
        }

        isFinalized = true;

        if (bestBidder == address(0)) {
            emit AuctionFinalized(address(0), 0, 0);
            return;
        }

        winner = bestBidder;
        winningBid = bestAmount;
        priceToPay = secondDistinct == type(uint256).max ? bestAmount : secondDistinct;
        winnerLockedDeposit = bidders[winner].deposit;

        emit AuctionFinalized(winner, winningBid, priceToPay);
    }

    /**
     * @dev No ganadores retiran su deposito tras finalizar.
     */
    function withdrawDeposit() external nonReentrant {
        require(isFinalized, "Auction not finalized");

        Bidder storage b = bidders[msg.sender];
        require(b.committed, "No committed bid");
        require(msg.sender != winner, "Winner deposit handled in delivery workflow");
        require(!b.depositWithdrawn, "Deposit already withdrawn");

        uint256 amount = b.deposit;
        require(amount > 0, "No deposit to withdraw");

        b.deposit = 0;
        b.depositWithdrawn = true;

        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        require(ok, "Withdraw transfer failed");
        emit DepositWithdrawn(msg.sender, amount);
    }

    /**
     * @dev Confirma entrega y paga al ganador: segundo precio + devolucion deposito.
     * msg.value debe ser exactamente el segundo precio.
     */
    function confirmDeliveryAndPay() external payable onlyHealthService nonReentrant {
        require(isFinalized, "Auction not finalized");
        require(winner != address(0), "No winner");
        require(!deliveryConfirmed, "Delivery already confirmed");
        require(!winnerPenalized, "Winner already penalized");
        require(block.timestamp <= deliveryDeadline, "Delivery deadline passed");
        require(msg.value == priceToPay, "Must fund exact second price");

        deliveryConfirmed = true;

        Bidder storage w = bidders[winner];
        uint256 refundDeposit = w.deposit;
        w.deposit = 0;
        w.depositWithdrawn = true;

        uint256 totalPayout = msg.value + refundDeposit;
        (bool ok, ) = payable(winner).call{value: totalPayout}("");
        require(ok, "Winner payment failed");

        emit DeliveryConfirmed(winner, totalPayout);
    }

    /**
     * @dev Penaliza al ganador si no entrega a tiempo: pierde deposito.
     */
    function markNonDelivery() external onlyHealthService nonReentrant {
        require(isFinalized, "Auction not finalized");
        require(winner != address(0), "No winner");
        require(!deliveryConfirmed, "Delivery already confirmed");
        require(!winnerPenalized, "Winner already penalized");
        require(block.timestamp > deliveryDeadline, "Delivery period still open");

        winnerPenalized = true;

        Bidder storage w = bidders[winner];
        uint256 penalty = w.deposit;
        w.deposit = 0;
        w.depositWithdrawn = true;

        if (penalty > 0) {
            (bool ok, ) = payable(healthService).call{value: penalty}("");
            require(ok, "Penalty transfer failed");
        }

        emit WinnerPenalized(winner, penalty);
    }

    /**
     * @dev Publica resultados una vez finalizada para auditabilidad.
     */
    function getAllRevealedBids()
        external
        view
        returns (address[] memory addresses, uint256[] memory amounts, bool[] memory revealed)
    {
        require(isFinalized, "Results available after finalize");

        uint256 len = bidderAddresses.length;
        addresses = new address[](len);
        amounts = new uint256[](len);
        revealed = new bool[](len);

        for (uint256 i = 0; i < len; i++) {
            address bidder = bidderAddresses[i];
            Bidder storage b = bidders[bidder];
            addresses[i] = bidder;
            amounts[i] = b.revealedBid;
            revealed[i] = b.hasRevealed;
        }
    }

    function bidderCount() external view returns (uint256) {
        return bidderAddresses.length;
    }
}

/**
 * @title HealthProcurementAuctionFactory
 * @dev Permite inicializar ilimitadas subastas con parametros independientes.
 */
contract HealthProcurementAuctionFactory {
    address[] public auctions;

    event AuctionCreated(
        address indexed auction,
        address indexed healthService,
        uint256 auctionStart,
        uint256 biddingDeadline,
        uint256 revealDeadline,
        uint256 deliveryDeadline,
        uint256 maxAcceptablePrice
    );

    function createAuction(
        uint256 auctionStart,
        uint256 biddingDeadline,
        uint256 revealDeadline,
        uint256 deliveryDeadline,
        uint256 maxAcceptablePrice
    ) external returns (address) {
        HealthProcurementAuction auction = new HealthProcurementAuction(
            msg.sender,
            auctionStart,
            biddingDeadline,
            revealDeadline,
            deliveryDeadline,
            maxAcceptablePrice
        );

        address auctionAddress = address(auction);
        auctions.push(auctionAddress);

        emit AuctionCreated(
            auctionAddress,
            msg.sender,
            auctionStart,
            biddingDeadline,
            revealDeadline,
            deliveryDeadline,
            maxAcceptablePrice
        );

        return auctionAddress;
    }

    function getAuctionsCount() external view returns (uint256) {
        return auctions.length;
    }
}
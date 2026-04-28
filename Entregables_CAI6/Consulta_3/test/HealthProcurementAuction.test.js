const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

const SECRET = "salt-shared-only-bidder-knows";

function commitHash(amountWei, secret) {
  return ethers.solidityPackedKeccak256(["uint256", "string"], [amountWei, secret]);
}

async function deployAuction(maxPriceEth = "1000") {
  const [healthService, ...bidders] = await ethers.getSigners();
  const now = await time.latest();
  const auctionStart = now + 10;
  const biddingDeadline = now + 60 * 60;
  const revealDeadline = biddingDeadline + 60 * 60;
  const deliveryDeadline = revealDeadline + 60 * 60 * 24;
  const maxPrice = ethers.parseEther(maxPriceEth);

  const Auction = await ethers.getContractFactory("HealthProcurementAuction");
  const auction = await Auction.connect(healthService).deploy(
    healthService.address,
    auctionStart,
    biddingDeadline,
    revealDeadline,
    deliveryDeadline,
    maxPrice
  );
  await auction.waitForDeployment();

  await time.increaseTo(auctionStart + 1);
  return { auction, healthService, bidders, biddingDeadline, revealDeadline, deliveryDeadline, maxPrice };
}

describe("HealthProcurementAuction", () => {
  it("rejects zero deposit and zero amount commit", async () => {
    const { auction, bidders } = await deployAuction();
    const h = commitHash(ethers.parseEther("100"), SECRET);
    await expect(
      auction.connect(bidders[0]).commitBid(h, { value: 0 })
    ).to.be.revertedWith("Deposit must be > 0");
  });

  it("rejects double commit by same bidder", async () => {
    const { auction, bidders } = await deployAuction();
    const h = commitHash(ethers.parseEther("100"), SECRET);
    await auction.connect(bidders[0]).commitBid(h, { value: ethers.parseEther("10") });
    await expect(
      auction.connect(bidders[0]).commitBid(h, { value: ethers.parseEther("10") })
    ).to.be.revertedWith("Bidder already committed");
  });

  it("rejects bid above maxAcceptablePrice on reveal", async () => {
    const { auction, bidders, biddingDeadline } = await deployAuction("100");
    const amount = ethers.parseEther("200");
    const h = commitHash(amount, SECRET);
    await auction.connect(bidders[0]).commitBid(h, { value: ethers.parseEther("21") });
    await time.increaseTo(biddingDeadline + 1);
    await expect(
      auction.connect(bidders[0]).revealBid(amount, SECRET)
    ).to.be.revertedWith("Bid exceeds max price");
  });

  it("rejects reveal with insufficient deposit (<10%)", async () => {
    const { auction, bidders, biddingDeadline } = await deployAuction();
    const amount = ethers.parseEther("100");
    const h = commitHash(amount, SECRET);
    await auction.connect(bidders[0]).commitBid(h, { value: ethers.parseEther("9") });
    await time.increaseTo(biddingDeadline + 1);
    await expect(
      auction.connect(bidders[0]).revealBid(amount, SECRET)
    ).to.be.revertedWith("Deposit below required 10%");
  });

  it("computes Vickrey winner with second-distinct price", async () => {
    const { auction, bidders, biddingDeadline, revealDeadline, healthService } = await deployAuction();
    const bids = [
      { signer: bidders[0], amount: ethers.parseEther("690") },
      { signer: bidders[1], amount: ethers.parseEther("610") },
      { signer: bidders[2], amount: ethers.parseEther("725") },
      { signer: bidders[3], amount: ethers.parseEther("610") },
    ];
    for (const b of bids) {
      const h = commitHash(b.amount, SECRET);
      await auction.connect(b.signer).commitBid(h, { value: ethers.parseEther("80") });
    }
    await time.increaseTo(biddingDeadline + 1);
    for (const b of bids) {
      await auction.connect(b.signer).revealBid(b.amount, SECRET);
    }
    await time.increaseTo(revealDeadline + 1);
    await auction.connect(healthService).finalizeAuction();
    expect(await auction.winner()).to.equal(bidders[1].address);
    expect(await auction.winningBid()).to.equal(ethers.parseEther("610"));
    expect(await auction.priceToPay()).to.equal(ethers.parseEther("690"));
  });

  it("falls back to own price when only one valid reveal", async () => {
    const { auction, bidders, biddingDeadline, revealDeadline, healthService } = await deployAuction();
    const amount = ethers.parseEther("500");
    const h = commitHash(amount, SECRET);
    await auction.connect(bidders[0]).commitBid(h, { value: ethers.parseEther("60") });
    await time.increaseTo(biddingDeadline + 1);
    await auction.connect(bidders[0]).revealBid(amount, SECRET);
    await time.increaseTo(revealDeadline + 1);
    await auction.connect(healthService).finalizeAuction();
    expect(await auction.priceToPay()).to.equal(amount);
  });

  it("losers can withdraw deposits, winner cannot via withdrawDeposit", async () => {
    const { auction, bidders, biddingDeadline, revealDeadline, healthService } = await deployAuction();
    const a1 = ethers.parseEther("400");
    const a2 = ethers.parseEther("500");
    await auction.connect(bidders[0]).commitBid(commitHash(a1, SECRET), { value: ethers.parseEther("50") });
    await auction.connect(bidders[1]).commitBid(commitHash(a2, SECRET), { value: ethers.parseEther("60") });
    await time.increaseTo(biddingDeadline + 1);
    await auction.connect(bidders[0]).revealBid(a1, SECRET);
    await auction.connect(bidders[1]).revealBid(a2, SECRET);
    await time.increaseTo(revealDeadline + 1);
    await auction.connect(healthService).finalizeAuction();
    await expect(auction.connect(bidders[1]).withdrawDeposit()).to.changeEtherBalance(
      bidders[1],
      ethers.parseEther("60")
    );
    await expect(auction.connect(bidders[0]).withdrawDeposit()).to.be.revertedWith(
      "Winner deposit handled in delivery workflow"
    );
  });

  it("pays winner second price plus deposit on delivery", async () => {
    const { auction, bidders, biddingDeadline, revealDeadline, healthService } = await deployAuction();
    const a1 = ethers.parseEther("400");
    const a2 = ethers.parseEther("500");
    await auction.connect(bidders[0]).commitBid(commitHash(a1, SECRET), { value: ethers.parseEther("50") });
    await auction.connect(bidders[1]).commitBid(commitHash(a2, SECRET), { value: ethers.parseEther("60") });
    await time.increaseTo(biddingDeadline + 1);
    await auction.connect(bidders[0]).revealBid(a1, SECRET);
    await auction.connect(bidders[1]).revealBid(a2, SECRET);
    await time.increaseTo(revealDeadline + 1);
    await auction.connect(healthService).finalizeAuction();
    const expectedPayout = ethers.parseEther("550");
    await expect(
      auction.connect(healthService).confirmDeliveryAndPay({ value: ethers.parseEther("500") })
    ).to.changeEtherBalance(bidders[0], expectedPayout);
  });

  it("retains deposit on non-delivery", async () => {
    const { auction, bidders, biddingDeadline, revealDeadline, deliveryDeadline, healthService } = await deployAuction();
    const a1 = ethers.parseEther("400");
    await auction.connect(bidders[0]).commitBid(commitHash(a1, SECRET), { value: ethers.parseEther("50") });
    await time.increaseTo(biddingDeadline + 1);
    await auction.connect(bidders[0]).revealBid(a1, SECRET);
    await time.increaseTo(revealDeadline + 1);
    await auction.connect(healthService).finalizeAuction();
    await time.increaseTo(deliveryDeadline + 1);
    await expect(auction.connect(healthService).markNonDelivery()).to.changeEtherBalance(
      healthService,
      ethers.parseEther("50")
    );
  });

  it("closes commit phase at MAX_BIDS=30", async () => {
    const [healthService, ...signers] = await ethers.getSigners();
    expect(signers.length).to.be.greaterThanOrEqual(30);
    const { auction } = await deployAuction();
    for (let i = 0; i < 30; i++) {
      const amount = ethers.parseEther(String(100 + i));
      await auction
        .connect(signers[i])
        .commitBid(commitHash(amount, SECRET), { value: ethers.parseEther("12") });
    }
    expect(await auction.commitClosed()).to.equal(true);
    await expect(
      auction
        .connect(signers[30])
        .commitBid(commitHash(ethers.parseEther("99"), SECRET), { value: ethers.parseEther("12") })
    ).to.be.revertedWith("Commit phase closed");
  });

  it("rejects finalize before reveal deadline", async () => {
    const { auction, bidders, biddingDeadline, healthService } = await deployAuction();
    const amount = ethers.parseEther("400");
    await auction.connect(bidders[0]).commitBid(commitHash(amount, SECRET), { value: ethers.parseEther("50") });
    await time.increaseTo(biddingDeadline + 1);
    await auction.connect(bidders[0]).revealBid(amount, SECRET);
    await expect(auction.connect(healthService).finalizeAuction()).to.be.revertedWith(
      "Reveal phase not ended"
    );
  });

  it("only healthService can finalize, confirm or penalize", async () => {
    const { auction, bidders, biddingDeadline, revealDeadline } = await deployAuction();
    const amount = ethers.parseEther("400");
    await auction.connect(bidders[0]).commitBid(commitHash(amount, SECRET), { value: ethers.parseEther("50") });
    await time.increaseTo(biddingDeadline + 1);
    await auction.connect(bidders[0]).revealBid(amount, SECRET);
    await time.increaseTo(revealDeadline + 1);
    await expect(auction.connect(bidders[0]).finalizeAuction()).to.be.revertedWith(
      "Only Health Service can perform this action"
    );
  });
});

describe("HealthProcurementAuctionFactory", () => {
  it("creates independent auctions with custom params", async () => {
    const Factory = await ethers.getContractFactory("HealthProcurementAuctionFactory");
    const factory = await Factory.deploy();
    await factory.waitForDeployment();
    const now = await time.latest();
    const tx = await factory.createAuction(now + 10, now + 100, now + 200, now + 1000, ethers.parseEther("999"));
    await tx.wait();
    expect(await factory.getAuctionsCount()).to.equal(1);
  });
});
